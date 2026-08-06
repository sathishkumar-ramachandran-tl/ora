"""
Agentic RBAC — lets an org admin manage roles/permissions through natural language
("give Priya access to project financials but not billing") instead of only a settings
form. Follows the same shared-registry pattern as app/tools/task_tools.py: plain
functions returning {success, data, error}, called by both the LangChain orchestrator
and the MCP server.

SECURITY: every mutating function requires `acting_user_id` and re-checks that user's
own `org.manage_roles` permission before doing anything — the agent can never grant more
access than the requesting human already has, and a prompt-injected instruction from
someone without that permission is rejected here, not just at the UI layer. Bind
`acting_user_id` from the authenticated JWT identity server-side when constructing the
LangChain tool closures (see app/agents/tools.py) — never accept it as an LLM-suppliable
argument.
"""
import logging

from ..core.extensions import db
from .models import Organization, OrganizationMember, CustomRole
from .permissions import PERMISSIONS, check_permission, get_member_permissions

logger = logging.getLogger(__name__)


def _ok(data):
    return {"success": True, "data": data, "error": None}


def _fail(error: str):
    return {"success": False, "data": None, "error": error}


def _require_manage_roles(acting_user_id: str, organization_id: str):
    if not check_permission(acting_user_id, organization_id, "org.manage_roles"):
        logger.warning(
            "rbac_denied",
            extra={"acting_user_id": acting_user_id, "organization_id": organization_id},
        )
        return _fail("You don't have permission to manage roles in this organization")
    return None


def list_permission_catalog() -> dict:
    return _ok([{"key": k, "description": v} for k, v in PERMISSIONS.items()])


def list_roles(organization_id: str) -> dict:
    roles = CustomRole.query.filter_by(organization_id=organization_id).all()
    return _ok([{
        "id": r.id, "name": r.name, "permissions": r.permissions or [], "isSystem": r.is_system,
    } for r in roles])


def list_members_with_permissions(organization_id: str) -> dict:
    members = OrganizationMember.query.filter_by(organization_id=organization_id).all()
    return _ok([{
        "user_id": m.user_id, "role": m.role, "custom_role_id": m.custom_role_id,
        "permissions": get_member_permissions(m),
    } for m in members])


def create_custom_role(acting_user_id: str, organization_id: str, name: str, permissions: list[str]) -> dict:
    denial = _require_manage_roles(acting_user_id, organization_id)
    if denial:
        return denial

    valid_permissions = [p for p in permissions if p in PERMISSIONS]
    invalid = set(permissions) - set(valid_permissions)
    if invalid:
        return _fail(f"Unknown permission(s): {', '.join(sorted(invalid))}")

    role = CustomRole(organization_id=organization_id, name=name, permissions=valid_permissions)
    db.session.add(role)
    db.session.commit()
    logger.info("rbac_role_created", extra={
        "acting_user_id": acting_user_id, "organization_id": organization_id,
        "role_id": role.id, "permissions": valid_permissions,
    })
    return _ok({"id": role.id, "name": role.name, "permissions": role.permissions})


def update_role_permissions(acting_user_id: str, organization_id: str, role_id: str, permissions: list[str]) -> dict:
    denial = _require_manage_roles(acting_user_id, organization_id)
    if denial:
        return denial

    role = CustomRole.query.filter_by(id=role_id, organization_id=organization_id).first()
    if not role:
        return _fail(f"Role {role_id} not found in this organization")

    valid_permissions = [p for p in permissions if p in PERMISSIONS]
    role.permissions = valid_permissions
    db.session.commit()
    logger.info("rbac_role_updated", extra={
        "acting_user_id": acting_user_id, "organization_id": organization_id,
        "role_id": role.id, "permissions": valid_permissions,
    })
    return _ok({"id": role.id, "name": role.name, "permissions": role.permissions})


def delete_custom_role(acting_user_id: str, organization_id: str, role_id: str) -> dict:
    denial = _require_manage_roles(acting_user_id, organization_id)
    if denial:
        return denial

    role = CustomRole.query.filter_by(id=role_id, organization_id=organization_id).first()
    if not role:
        return _fail(f"Role {role_id} not found in this organization")
    if role.is_system:
        return _fail(f"'{role.name}' is a system default role and cannot be deleted")

    OrganizationMember.query.filter_by(custom_role_id=role.id).update({"custom_role_id": None})
    db.session.delete(role)
    db.session.commit()
    logger.info("rbac_role_deleted", extra={
        "acting_user_id": acting_user_id, "organization_id": organization_id, "role_id": role_id,
    })
    return _ok({"deleted_role_id": role_id})


def assign_role_to_member(acting_user_id: str, organization_id: str, target_user_id: str, role_id: str) -> dict:
    denial = _require_manage_roles(acting_user_id, organization_id)
    if denial:
        return denial

    member = OrganizationMember.query.filter_by(organization_id=organization_id, user_id=target_user_id).first()
    if not member:
        return _fail(f"User {target_user_id} is not a member of this organization")
    if member.role == "owner":
        return _fail("Cannot reassign the organization owner's role")

    role = CustomRole.query.filter_by(id=role_id, organization_id=organization_id).first()
    if not role:
        return _fail(f"Role {role_id} not found in this organization")

    member.custom_role_id = role.id
    db.session.commit()
    logger.info("rbac_role_assigned", extra={
        "acting_user_id": acting_user_id, "organization_id": organization_id,
        "target_user_id": target_user_id, "role_id": role.id,
    })
    return _ok({"user_id": target_user_id, "assigned_role": role.name})


def grant_permission(acting_user_id: str, organization_id: str, target_user_id: str, permission: str) -> dict:
    """Convenience for a single-permission grant: adds `permission` to the member's
    current effective permission set via a dedicated per-user custom role, rather than
    requiring the caller to pre-create a role first."""
    denial = _require_manage_roles(acting_user_id, organization_id)
    if denial:
        return denial
    if permission not in PERMISSIONS:
        return _fail(f"Unknown permission: {permission}")

    member = OrganizationMember.query.filter_by(organization_id=organization_id, user_id=target_user_id).first()
    if not member:
        return _fail(f"User {target_user_id} is not a member of this organization")
    if member.role == "owner":
        return _fail("The organization owner already has every permission")

    current = set(get_member_permissions(member))
    current.add(permission)

    if member.custom_role_id:
        role = db.session.get(CustomRole, member.custom_role_id)
        role.permissions = sorted(current)
    else:
        role = CustomRole(
            organization_id=organization_id,
            name=f"Custom ({target_user_id[:8]})",
            permissions=sorted(current),
        )
        db.session.add(role)
        db.session.flush()
        member.custom_role_id = role.id

    db.session.commit()
    logger.info("rbac_permission_granted", extra={
        "acting_user_id": acting_user_id, "organization_id": organization_id,
        "target_user_id": target_user_id, "permission": permission,
    })
    return _ok({"user_id": target_user_id, "granted": permission, "effective_permissions": sorted(current)})


def revoke_permission(acting_user_id: str, organization_id: str, target_user_id: str, permission: str) -> dict:
    denial = _require_manage_roles(acting_user_id, organization_id)
    if denial:
        return denial

    member = OrganizationMember.query.filter_by(organization_id=organization_id, user_id=target_user_id).first()
    if not member:
        return _fail(f"User {target_user_id} is not a member of this organization")
    if member.role == "owner":
        return _fail("Cannot revoke permissions from the organization owner")
    if not member.custom_role_id:
        return _fail(f"User {target_user_id} has no custom role to revoke a permission from")

    role = db.session.get(CustomRole, member.custom_role_id)
    current = set(role.permissions or [])
    current.discard(permission)
    role.permissions = sorted(current)
    db.session.commit()
    logger.info("rbac_permission_revoked", extra={
        "acting_user_id": acting_user_id, "organization_id": organization_id,
        "target_user_id": target_user_id, "permission": permission,
    })
    return _ok({"user_id": target_user_id, "revoked": permission, "effective_permissions": sorted(current)})
