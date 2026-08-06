from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..auth.models import User
from .models import Workspace, WorkspaceMember

workspace_bp = Blueprint('workspace', __name__)


@workspace_bp.route('/workspaces', methods=['POST'])
@jwt_required()
def create_workspace():
    """
    Create a Workspace.
    context: 'personal' | 'company' — company workspaces require organization_id.
    type: 'study' | 'project'
    """
    from ..projects.models import Company

    user_id = get_jwt_identity()
    data = request.json or {}
    ws_data = data.get('workspace', data)  # accept either {workspace: {...}} or a flat body

    context = ws_data.get('context', 'personal')
    organization_id = ws_data.get('organizationId') or ws_data.get('organization_id')
    if context == 'company' and not organization_id:
        return jsonify({"error": "organization_id is required for a company workspace"}), 400

    if context == 'company':
        from ..organizations.permissions import check_permission
        if not check_permission(user_id, organization_id, 'workspace.create'):
            return jsonify({"error": "You don't have permission to create a workspace in this organization"}), 403

    from ..billing import service as billing_service
    sub = billing_service.get_subscription(
        user_id=user_id if context == 'personal' else None,
        organization_id=organization_id if context == 'company' else None,
    )
    if not sub:
        sub = billing_service.create_trial_subscription(
            user_id=user_id if context == 'personal' else None,
            organization_id=organization_id if context == 'company' else None,
        )
    limit_check = billing_service.check_limit(sub, 'workspaces')
    if not limit_check['allowed']:
        return jsonify({
            "error": f"Workspace limit reached for your plan ({limit_check['current']}/{limit_check['limit']}). Upgrade to create more.",
            "code": "limit_reached",
            "resource": "workspaces",
        }), 402

    ws = Workspace(
        id=ws_data.get('id'),
        name=ws_data['name'],
        type=ws_data.get('type', 'project'),
        context=context,
        persona=ws_data.get('persona', 'general'),
        owner_id=user_id if context == 'personal' else None,
        organization_id=organization_id if context == 'company' else None,
        description=ws_data.get('description'),
        company_website=ws_data.get('companyWebsite'),
        location=ws_data.get('location'),
        employee_count=ws_data.get('employeeCount'),
        category=ws_data.get('category'),
        ai_context_description=ws_data.get('aiContextDescription'),
    )
    db.session.add(ws)
    db.session.flush()

    db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=user_id, role_id='owner'))
    db.session.flush()

    if ws.type == 'study' or context == 'personal':
        db.session.add(Company(workspace_id=ws.id, name='General', mission='General tasks', color='slate'))

    db.session.commit()
    return jsonify({"status": "created", "id": ws.id, "type": ws.type, "context": ws.context}), 201


@workspace_bp.route('/users/<user_id>/workspaces', methods=['GET'])
@jwt_required()
def get_user_workspaces(user_id):
    if user_id != get_jwt_identity():
        return jsonify({"error": "Forbidden"}), 403

    memberships = WorkspaceMember.query.filter_by(user_id=user_id).all()
    workspaces = []
    for m in memberships:
        ws = db.session.get(Workspace, m.workspace_id)
        if ws:
            workspaces.append({
                "id": ws.id, "name": ws.name, "type": ws.type, "context": ws.context,
                "persona": ws.persona, "organizationId": ws.organization_id, "role": m.role_id,
            })
    return jsonify(workspaces)


@workspace_bp.route('/workspaces/<ws_id>/full-state', methods=['GET'])
@jwt_required()
def get_full_state(ws_id):
    from ..projects.models import Company, Project, ProjectMember
    from ..tasks.models import Task

    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    is_member = WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=current_user).first() is not None
    if not is_member and workspace.owner_id != current_user:
        return jsonify({"error": "Forbidden"}), 403

    companies = Company.query.filter_by(workspace_id=ws_id).all()
    result = []

    for c in companies:
        projects = Project.query.filter_by(company_id=c.id).all()
        c_data = {
            "id": c.id, "workspaceId": c.workspace_id, "name": c.name, "mission": c.mission,
            "color": c.color, "whiteboard": c.whiteboard, "projects": []
        }
        for p in projects:
            is_owner = workspace and workspace.owner_id == current_user
            has_project_access = ProjectMember.query.filter_by(project_id=p.id, user_id=current_user).first() is not None

            if is_owner or has_project_access:
                tasks = Task.query.filter_by(project_id=p.id).all()
                c_data['projects'].append({
                    "id": p.id, "workspaceId": p.workspace_id, "companyId": p.company_id,
                    "name": p.name, "type": p.type, "mission": p.mission, "progress": p.progress,
                    "whiteboard": p.whiteboard,
                    "tasks": [{
                        "id": t.id, "workspaceId": t.workspace_id, "title": t.title,
                        "description": t.description, "status": t.status, "priority": t.priority,
                        "estimatedHours": t.estimated_hours, "isDailyFocus": t.is_daily_focus,
                        "resources": t.resources,
                        "dueDate": t.due_date.isoformat() if t.due_date else None,
                        "labels": t.labels or [], "assigneeId": t.assignee_id,
                        "issueType": t.issue_type or "task",
                        "projectId": t.project_id, "milestoneId": t.milestone_id,
                        "sprintId": t.sprint_id, "parentTaskId": t.parent_task_id,
                    } for t in tasks]
                })
        result.append(c_data)

    return jsonify(result)


@workspace_bp.route('/workspaces/<ws_id>', methods=['PATCH'])
@jwt_required()
def update_workspace(ws_id):
    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can update settings"}), 403

    data = request.json or {}
    if data.get('name'): workspace.name = data['name']
    if data.get('companyWebsite') is not None: workspace.company_website = data['companyWebsite']
    if data.get('location') is not None: workspace.location = data['location']
    if data.get('employeeCount') is not None: workspace.employee_count = data['employeeCount']
    if data.get('aiContextDescription') is not None: workspace.ai_context_description = data['aiContextDescription']
    db.session.commit()
    return jsonify({"status": "updated"})


# --- Member management ---

@workspace_bp.route('/workspaces/<ws_id>/members', methods=['GET'])
@jwt_required()
def get_workspace_members(ws_id):
    current_user = get_jwt_identity()
    if not WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=current_user).first():
        return jsonify({"error": "Forbidden"}), 403

    members = WorkspaceMember.query.filter_by(workspace_id=ws_id).all()
    result = []
    for m in members:
        user = db.session.get(User, m.user_id)
        if user:
            result.append({
                # WorkspaceMember has a composite (workspace_id, user_id) primary key, not a
                # standalone id column — expose user_id as "id" so DELETE /members/<id> below
                # (scoped by ws_id in the URL already) can look it up directly.
                "id": m.user_id, "userId": m.user_id, "name": user.name,
                "email": user.email, "avatar": user.avatar, "role": m.role_id,
                "joinedAt": m.joined_at.isoformat() if m.joined_at else None,
            })
    return jsonify(result)


@workspace_bp.route('/workspaces/<ws_id>/invite', methods=['POST'])
@jwt_required()
def invite_to_workspace(ws_id):
    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can invite members"}), 403

    data = request.json or {}
    email = data.get('email')
    role = data.get('role', 'contributor')
    if not email:
        return jsonify({"error": "Email required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=email.split('@')[0])
        db.session.add(user)
        db.session.commit()

    if WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=user.id).first():
        return jsonify({"error": "User already in workspace"}), 400

    db.session.add(WorkspaceMember(workspace_id=ws_id, user_id=user.id, role_id=role))
    db.session.commit()
    return jsonify({"status": "invited", "userId": user.id}), 201


@workspace_bp.route('/workspaces/<ws_id>/members/<user_id>', methods=['DELETE'])
@jwt_required()
def remove_workspace_member(ws_id, user_id):
    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can remove members"}), 403

    member = WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=user_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404

    db.session.delete(member)
    db.session.commit()
    return jsonify({"status": "removed"}), 200
