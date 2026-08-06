from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..core.authz import user_can_access_workspace, user_can_access_task
from ..tools import task_tools
from .models import Task

task_bp = Blueprint('task', __name__)


def _from_tool(result):
    if result.get("success"):
        return jsonify(result["data"])
    error = result.get("error") or "Not found"
    status = 404 if "not found" in error.lower() else 400
    return jsonify({"error": error}), status


@task_bp.route('/projects/<p_id>/tasks', methods=['POST'])
@jwt_required()
def add_tasks(p_id):
    current_user = get_jwt_identity()
    tasks_data = (request.json or {}).get('tasks', [])

    for t_data in tasks_data:
        if not user_can_access_workspace(current_user, t_data.get('workspaceId')):
            return jsonify({"error": "Forbidden"}), 403

    for t_data in tasks_data:
        due_raw = t_data.get('dueDate')
        due_date = datetime.fromisoformat(due_raw) if due_raw else None
        t = Task(
            id=t_data.get('id'),
            workspace_id=t_data['workspaceId'],
            project_id=p_id,
            title=t_data['title'],
            description=t_data.get('description'),
            status=t_data['status'],
            priority=t_data['priority'],
            estimated_hours=t_data.get('estimatedHours'),
            due_date=due_date,
            labels=t_data.get('labels', []),
            assignee_id=t_data.get('assigneeId'),
            issue_type=t_data.get('issueType', 'task'),
        )
        db.session.add(t)
    db.session.commit()
    return jsonify({"status": "ok"})


@task_bp.route('/tasks/<task_id>', methods=['PATCH'])
@jwt_required()
def update_task(task_id):
    """Partial task update — backs updateTaskStatus/updateTaskResources/toggleTaskDailyFocus
    on the frontend. This endpoint didn't exist before (those calls were silently 404ing)."""
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not user_can_access_task(get_jwt_identity(), task):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    if 'title' in data: task.title = data['title']
    if 'description' in data: task.description = data['description']
    if 'status' in data: task.status = data['status']
    if 'priority' in data: task.priority = data['priority']
    if 'estimatedHours' in data: task.estimated_hours = data['estimatedHours']
    if 'isDailyFocus' in data: task.is_daily_focus = data['isDailyFocus']
    if 'resources' in data: task.resources = data['resources']
    if 'dueDate' in data:
        task.due_date = datetime.fromisoformat(data['dueDate']) if data['dueDate'] else None
    if 'labels' in data: task.labels = data['labels']
    if 'assigneeId' in data: task.assignee_id = data['assigneeId']
    if 'issueType' in data: task.issue_type = data['issueType']
    if 'milestoneId' in data: task.milestone_id = data['milestoneId']
    if 'sprintId' in data: task.sprint_id = data['sprintId']

    db.session.commit()
    return jsonify({"status": "updated", "id": task.id})


@task_bp.route('/tasks/<task_id>', methods=['DELETE'])
@jwt_required()
def delete_task(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not user_can_access_task(get_jwt_identity(), task):
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(task)
    db.session.commit()
    return jsonify({"status": "deleted"})


@task_bp.route('/tasks/<task_id>/dependencies', methods=['GET'])
@jwt_required()
def get_dependencies(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not user_can_access_task(get_jwt_identity(), task):
        return jsonify({"error": "Forbidden"}), 403
    return _from_tool(task_tools.get_task_dependencies(task_id))


@task_bp.route('/tasks/<task_id>/dependencies', methods=['POST'])
@jwt_required()
def add_dependency(task_id):
    task = db.session.get(Task, task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not user_can_access_task(get_jwt_identity(), task):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    depends_on_task_id = data.get('dependsOnTaskId')
    if not depends_on_task_id:
        return jsonify({"error": "dependsOnTaskId is required"}), 400

    result = task_tools.add_task_dependency(
        task_id, depends_on_task_id, data.get('type', 'blocks'),
    )
    if result.get("success"):
        return jsonify(result["data"]), 201
    return _from_tool(result)


@task_bp.route('/tasks/dependencies/<dependency_id>', methods=['DELETE'])
@jwt_required()
def remove_dependency(dependency_id):
    from ..projects.models import TaskDependency
    dep = db.session.get(TaskDependency, dependency_id)
    if not dep:
        return jsonify({"error": "Dependency not found"}), 404
    task = db.session.get(Task, dep.task_id)
    if not task or not user_can_access_task(get_jwt_identity(), task):
        return jsonify({"error": "Forbidden"}), 403
    return _from_tool(task_tools.remove_task_dependency(dependency_id))
