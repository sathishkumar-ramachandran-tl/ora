from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..core.authz import user_can_access_workspace
from ..auth.models import User
from ..workspaces.models import Workspace
from .models import Company, Project, ProjectMember, Milestone, Sprint
from ..tools import task_tools

project_bp = Blueprint('project', __name__)


def _from_tool(result, not_found_hint="Not found"):
    """Adapt a {"success","data","error"} task_tools result into a Flask response."""
    if result.get("success"):
        return jsonify(result["data"])
    error = result.get("error") or not_found_hint
    status = 404 if "not found" in error.lower() else 400
    return jsonify({"error": error}), status


@project_bp.route('/companies', methods=['POST'])
@jwt_required()
def add_company():
    data = request.json or {}
    data.pop('projects', None)
    if 'workspaceId' in data:
        data['workspace_id'] = data.pop('workspaceId')
    if not user_can_access_workspace(get_jwt_identity(), data.get('workspace_id')):
        return jsonify({"error": "Forbidden"}), 403

    c = Company(**data)
    db.session.add(c)
    db.session.commit()
    return jsonify({"status": "ok", "id": c.id})


@project_bp.route('/companies/<c_id>/projects', methods=['POST'])
@jwt_required()
def add_project(c_id):
    data = request.json or {}
    workspace_id = data.get('workspaceId')
    if not user_can_access_workspace(get_jwt_identity(), workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    p = Project(
        id=data.get('id'),
        workspace_id=workspace_id,
        company_id=c_id,
        name=data['name'],
        type=data['type'],
        mission=data.get('mission'),
        progress=0,
        whiteboard=data.get('whiteboard', []),
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({"status": "ok", "id": p.id})


# --- Whiteboard (SpatialCanvas) persistence — previously missing; saveWhiteboard() on the
# frontend was silently 404ing, so the infinite-canvas view never actually saved anything. ---

@project_bp.route('/companies/<c_id>/whiteboard', methods=['PATCH'])
@jwt_required()
def save_company_whiteboard(c_id):
    company = db.session.get(Company, c_id)
    if not company:
        return jsonify({"error": "Company not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), company.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    company.whiteboard = (request.json or {}).get('items', [])
    db.session.commit()
    return jsonify({"status": "saved"})


@project_bp.route('/projects/<p_id>/whiteboard', methods=['PATCH'])
@jwt_required()
def save_project_whiteboard(p_id):
    project = db.session.get(Project, p_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    project.whiteboard = (request.json or {}).get('items', [])
    db.session.commit()
    return jsonify({"status": "saved"})


# --- Project member management ---

@project_bp.route('/projects/<project_id>/members', methods=['GET'])
@jwt_required()
def get_project_members(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    result = []
    for m in members:
        user = db.session.get(User, m.user_id)
        if user:
            result.append({
                "id": m.id, "userId": m.user_id, "name": user.name, "email": user.email,
                "avatar": user.avatar, "role": m.role,
                "assignedAt": m.assigned_at.isoformat() if m.assigned_at else None,
            })
    return jsonify(result)


@project_bp.route('/projects/<project_id>/assign-member', methods=['POST'])
@jwt_required()
def assign_project_member(project_id):
    current_user = get_jwt_identity()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    workspace = db.session.get(Workspace, project.workspace_id)
    if not workspace or workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can assign members"}), 403

    data = request.json or {}
    user_id = data.get('userId')
    role = data.get('role', 'contributor')
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    if not db.session.get(User, user_id):
        return jsonify({"error": "User not found"}), 404
    if ProjectMember.query.filter_by(project_id=project_id, user_id=user_id).first():
        return jsonify({"error": "User already assigned to project"}), 400

    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.session.add(member)
    db.session.commit()
    return jsonify({"status": "assigned", "projectMemberId": member.id}), 201


@project_bp.route('/projects/<project_id>/members/<member_id>', methods=['DELETE'])
@jwt_required()
def unassign_project_member(project_id, member_id):
    current_user = get_jwt_identity()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404

    workspace = db.session.get(Workspace, project.workspace_id)
    if not workspace or workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can unassign members"}), 403

    member = db.session.get(ProjectMember, member_id)
    if not member or member.project_id != project_id:
        return jsonify({"error": "Member not found"}), 404

    db.session.delete(member)
    db.session.commit()
    return jsonify({"status": "unassigned"}), 200


# --- Milestones & Sprints (Phase-0 schema, surfaced here for Phase-4 PM work) ---

@project_bp.route('/projects/<project_id>/milestones', methods=['GET'])
@jwt_required()
def list_milestones(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    milestones = Milestone.query.filter_by(project_id=project_id).order_by(Milestone.order).all()
    return jsonify([{
        "id": m.id, "title": m.title, "description": m.description,
        "dueDate": m.due_date.isoformat() if m.due_date else None,
        "status": m.status, "order": m.order,
    } for m in milestones])


@project_bp.route('/projects/<project_id>/milestones', methods=['POST'])
@jwt_required()
def create_milestone(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    if not data.get('title'):
        return jsonify({"error": "title is required"}), 400
    m = Milestone(
        project_id=project_id, title=data['title'], description=data.get('description', ''),
        due_date=datetime.fromisoformat(data['dueDate']) if data.get('dueDate') else None,
        order=data.get('order', 0),
    )
    db.session.add(m)
    db.session.commit()
    return jsonify({"status": "created", "id": m.id}), 201


def _milestone_or_403(milestone_id):
    milestone = db.session.get(Milestone, milestone_id)
    if not milestone:
        return None, (jsonify({"error": "Milestone not found"}), 404)
    project = db.session.get(Project, milestone.project_id)
    if not project or not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return None, (jsonify({"error": "Forbidden"}), 403)
    return milestone, None


@project_bp.route('/projects/milestones/<milestone_id>', methods=['PATCH'])
@jwt_required()
def patch_milestone(milestone_id):
    milestone, err = _milestone_or_403(milestone_id)
    if err:
        return err
    data = request.json or {}
    return _from_tool(task_tools.update_milestone(
        milestone_id,
        title=data.get('title'), description=data.get('description'),
        due_date=data.get('dueDate'), status=data.get('status'), order=data.get('order'),
    ))


@project_bp.route('/projects/milestones/<milestone_id>', methods=['DELETE'])
@jwt_required()
def remove_milestone(milestone_id):
    milestone, err = _milestone_or_403(milestone_id)
    if err:
        return err
    return _from_tool(task_tools.delete_milestone(milestone_id))


@project_bp.route('/projects/<project_id>/sprints', methods=['GET'])
@jwt_required()
def get_sprints(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    return _from_tool(task_tools.list_sprints(project_id))


@project_bp.route('/projects/<project_id>/sprints', methods=['POST'])
@jwt_required()
def add_sprint(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    data = request.json or {}
    if not data.get('name'):
        return jsonify({"error": "name is required"}), 400
    result = task_tools.create_sprint(
        project_id, data['name'], data.get('startDate'), data.get('endDate'),
        data.get('status', 'planned'),
    )
    if result.get("success"):
        return jsonify(result["data"]), 201
    return jsonify({"error": result.get("error")}), 400


def _sprint_or_403(sprint_id):
    sprint = db.session.get(Sprint, sprint_id)
    if not sprint:
        return None, (jsonify({"error": "Sprint not found"}), 404)
    project = db.session.get(Project, sprint.project_id)
    if not project or not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return None, (jsonify({"error": "Forbidden"}), 403)
    return sprint, None


@project_bp.route('/projects/sprints/<sprint_id>', methods=['PATCH'])
@jwt_required()
def patch_sprint(sprint_id):
    sprint, err = _sprint_or_403(sprint_id)
    if err:
        return err
    data = request.json or {}
    return _from_tool(task_tools.update_sprint(
        sprint_id,
        name=data.get('name'), start_date=data.get('startDate'),
        end_date=data.get('endDate'), status=data.get('status'),
    ))


@project_bp.route('/projects/sprints/<sprint_id>', methods=['DELETE'])
@jwt_required()
def remove_sprint(sprint_id):
    sprint, err = _sprint_or_403(sprint_id)
    if err:
        return err
    return _from_tool(task_tools.delete_sprint(sprint_id))


@project_bp.route('/projects/<project_id>/blocked-tasks', methods=['GET'])
@jwt_required()
def blocked_tasks(project_id):
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(get_jwt_identity(), project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403
    return _from_tool(task_tools.get_blocked_tasks(project_id))


@project_bp.route('/projects/<project_id>/replan', methods=['POST'])
@jwt_required()
def replan_project(project_id):
    current_user = get_jwt_identity()
    project = db.session.get(Project, project_id)
    if not project:
        return jsonify({"error": "Project not found"}), 404
    if not user_can_access_workspace(current_user, project.workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    goal = data.get('goal')
    if not goal:
        return jsonify({"error": "goal is required"}), 400

    result = task_tools.replan_project(project_id, project.workspace_id, current_user, goal)
    return _from_tool(result)
