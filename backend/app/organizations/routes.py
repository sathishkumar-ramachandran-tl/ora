from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..auth.models import User
from .models import Organization, OrganizationMember, CustomRole
from .permissions import (
    PERMISSIONS, SYSTEM_ROLE_TEMPLATES, check_permission,
    require_permission, get_member_permissions,
)

org_bp = Blueprint('org', __name__)


def _seed_system_roles(organization_id: str) -> None:
    for name, perms in SYSTEM_ROLE_TEMPLATES.items():
        db.session.add(CustomRole(
            organization_id=organization_id, name=name, permissions=perms, is_system=True,
            color={"Admin": "indigo", "Member": "emerald", "Viewer": "slate"}.get(name, "slate"),
        ))


def _role_json(role: CustomRole) -> dict:
    return {
        "id": role.id, "name": role.name, "color": role.color,
        "permissions": role.permissions or [], "isSystem": role.is_system,
    }


# ---------------------------------------------------------------------------
# Organization CRUD
# ---------------------------------------------------------------------------

@org_bp.route('/', methods=['POST'])
@jwt_required()
def create_organization():
    uid = get_jwt_identity()
    data = request.json or {}
    name = data.get('name')
    if not name:
        return jsonify({"error": "Organization name is required"}), 400

    org = Organization(name=name, domain=data.get('domain'), owner_id=uid, settings=data.get('settings', {}))
    db.session.add(org)
    db.session.flush()

    db.session.add(OrganizationMember(organization_id=org.id, user_id=uid, role='owner', status='active'))
    _seed_system_roles(org.id)
    db.session.commit()

    from ..billing.service import create_trial_subscription
    try:
        create_trial_subscription(organization_id=org.id)
    except Exception:
        current_app.logger.exception("Failed to create trial subscription for org %s", org.id)

    return jsonify({
        "message": "Organization created successfully",
        "organization": {"id": org.id, "name": org.name, "role": "owner"}
    }), 201


@org_bp.route('/', methods=['GET'])
@jwt_required()
def get_my_organizations():
    uid = get_jwt_identity()
    memberships = OrganizationMember.query.filter_by(user_id=uid).all()
    results = []
    for m in memberships:
        org = db.session.get(Organization, m.organization_id)
        if org:
            results.append({"id": org.id, "name": org.name, "domain": org.domain, "role": m.role})
    return jsonify(results)


@org_bp.route('/<org_id>', methods=['PATCH'])
@jwt_required()
@require_permission('org.manage_settings')
def update_organization(org_id):
    org = db.session.get(Organization, org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
    data = request.json or {}
    if data.get('name'): org.name = data['name']
    if data.get('domain') is not None: org.domain = data['domain']
    if data.get('settings') is not None: org.settings = data['settings']
    db.session.commit()
    return jsonify({"status": "updated"})


# ---------------------------------------------------------------------------
# Admin Console — dashboard + members
# ---------------------------------------------------------------------------

@org_bp.route('/<org_id>/dashboard', methods=['GET'])
@jwt_required()
@require_permission('org.view_members')
def get_org_dashboard(org_id):
    from ..workspaces.models import Workspace

    member_count = OrganizationMember.query.filter_by(organization_id=org_id).count()
    workspace_count = Workspace.query.filter_by(organization_id=org_id).count()

    recent = db.session.query(User, OrganizationMember).join(
        OrganizationMember, User.id == OrganizationMember.user_id
    ).filter(OrganizationMember.organization_id == org_id).order_by(OrganizationMember.joined_at.desc()).limit(5).all()

    return jsonify({
        "stats": {
            "totalMembers": member_count,
            "totalWorkspaces": workspace_count,
            "activeProjects": 0,
        },
        "recentMembers": [{
            "id": u.id, "name": u.name, "email": u.email, "role": m.role, "status": m.status
        } for u, m in recent]
    })


@org_bp.route('/<org_id>/members', methods=['GET'])
@jwt_required()
@require_permission('org.view_members')
def list_org_members(org_id):
    members = db.session.query(User, OrganizationMember).join(
        OrganizationMember, User.id == OrganizationMember.user_id
    ).filter(OrganizationMember.organization_id == org_id).all()

    return jsonify([{
        "id": u.id, "name": u.name, "email": u.email, "role": m.role,
        "customRoleId": m.custom_role_id, "status": m.status,
        "joinedAt": m.joined_at.isoformat(),
        "permissions": get_member_permissions(m),
    } for u, m in members])


@org_bp.route('/<org_id>/members', methods=['POST'])
@jwt_required()
@require_permission('org.manage_members')
def invite_member(org_id):
    data = request.json or {}
    email = data.get('email')
    role = data.get('role', 'member')
    if not email:
        return jsonify({"error": "Email required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=email.split('@')[0], is_onboarded=False)
        db.session.add(user)
        db.session.flush()

    if OrganizationMember.query.filter_by(organization_id=org_id, user_id=user.id).first():
        return jsonify({"error": "User already in organization"}), 400

    db.session.add(OrganizationMember(organization_id=org_id, user_id=user.id, role=role, status='invited'))
    db.session.commit()

    return jsonify({"message": "User invited", "member": {"id": user.id, "email": user.email, "role": role, "status": "invited"}}), 201


@org_bp.route('/<org_id>/members/<user_id>', methods=['PUT'])
@jwt_required()
@require_permission('org.manage_roles')
def update_member_role(org_id, user_id):
    data = request.json or {}
    member = OrganizationMember.query.filter_by(organization_id=org_id, user_id=user_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
    if member.role == 'owner':
        return jsonify({"error": "Cannot modify the organization owner's role"}), 400

    if data.get('role'):
        member.role = data['role']
    if 'customRoleId' in data:
        member.custom_role_id = data['customRoleId']
    db.session.commit()
    return jsonify({"status": "updated"})


@org_bp.route('/<org_id>/members/<user_id>', methods=['DELETE'])
@jwt_required()
@require_permission('org.manage_members')
def remove_member(org_id, user_id):
    member = OrganizationMember.query.filter_by(organization_id=org_id, user_id=user_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
    if member.role == 'owner':
        return jsonify({"error": "Cannot remove the organization owner"}), 400
    db.session.delete(member)
    db.session.commit()
    return jsonify({"status": "removed"})


# ---------------------------------------------------------------------------
# Custom Roles (granular RBAC)
# ---------------------------------------------------------------------------

@org_bp.route('/<org_id>/permissions', methods=['GET'])
@jwt_required()
@require_permission('org.view_members')
def list_permission_catalog(org_id):
    return jsonify([{"key": k, "description": v} for k, v in PERMISSIONS.items()])


@org_bp.route('/<org_id>/roles', methods=['GET'])
@jwt_required()
@require_permission('org.view_members')
def list_roles(org_id):
    roles = CustomRole.query.filter_by(organization_id=org_id).all()
    return jsonify([_role_json(r) for r in roles])


@org_bp.route('/<org_id>/roles', methods=['POST'])
@jwt_required()
@require_permission('org.manage_roles')
def create_role(org_id):
    data = request.json or {}
    name = data.get('name')
    permissions = [p for p in data.get('permissions', []) if p in PERMISSIONS]
    if not name:
        return jsonify({"error": "Role name is required"}), 400

    role = CustomRole(organization_id=org_id, name=name, permissions=permissions, color=data.get('color', 'indigo'))
    db.session.add(role)
    db.session.commit()
    return jsonify(_role_json(role)), 201


@org_bp.route('/<org_id>/roles/<role_id>', methods=['PATCH'])
@jwt_required()
@require_permission('org.manage_roles')
def update_role(org_id, role_id):
    role = CustomRole.query.filter_by(id=role_id, organization_id=org_id).first()
    if not role:
        return jsonify({"error": "Role not found"}), 404

    data = request.json or {}
    if data.get('name'): role.name = data['name']
    if data.get('color'): role.color = data['color']
    if 'permissions' in data:
        role.permissions = [p for p in data['permissions'] if p in PERMISSIONS]
    db.session.commit()
    return jsonify(_role_json(role))


@org_bp.route('/<org_id>/roles/<role_id>', methods=['DELETE'])
@jwt_required()
@require_permission('org.manage_roles')
def delete_role(org_id, role_id):
    role = CustomRole.query.filter_by(id=role_id, organization_id=org_id).first()
    if not role:
        return jsonify({"error": "Role not found"}), 404
    if role.is_system:
        return jsonify({"error": "Cannot delete a system default role"}), 400

    OrganizationMember.query.filter_by(custom_role_id=role.id).update({"custom_role_id": None})
    db.session.delete(role)
    db.session.commit()
    return jsonify({"status": "deleted"})
