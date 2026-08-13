"""
Task / project / initiative business logic — shared by the LangChain orchestrator
(app/agents/tools.py) and the MCP server (app/mcp_server.py).

Every function here runs inside a Flask application context (for db.session access)
and returns the canonical {"success": bool, "data": ..., "error": str | None} shape,
regardless of caller.
"""
import uuid
import json
from typing import Optional


def _get_db():
    from ..core.extensions import db
    return db


def _get_models():
    from .. import models
    return models


def _ok(data) -> dict:
    return {"success": True, "data": data, "error": None}


def _fail(error: str) -> dict:
    return {"success": False, "data": None, "error": error}


def _ctx():
    try:
        from ..agents.execution_context import get_execution_context
        return get_execution_context(required=False)
    except Exception:
        return None


def require_workspace_access(ctx, workspace_id: str) -> Optional[str]:
    if ctx is None:
        return None
    if workspace_id != ctx.workspace_id:
        return "Unauthorized: resource is outside the trusted workspace"
    from ..core.authz import user_can_access_workspace
    if not user_can_access_workspace(ctx.user_id, workspace_id):
        return "Unauthorized: user cannot access this workspace"
    return None


def require_project_access(ctx, project_id: str) -> tuple[Optional[object], Optional[str]]:
    db = _get_db()
    m = _get_models()
    project = db.session.get(m.Project, project_id)
    if not project:
        return None, f"Project {project_id} not found"
    error = require_workspace_access(ctx, project.workspace_id)
    if error:
        return None, error
    return project, None


def require_task_access(ctx, task_id: str) -> tuple[Optional[object], Optional[str]]:
    db = _get_db()
    m = _get_models()
    task = db.session.get(m.Task, task_id)
    if not task:
        return None, f"Task {task_id} not found"
    error = require_workspace_access(ctx, task.workspace_id)
    if error:
        return None, error
    return task, None


def require_milestone_access(ctx, milestone_id: str) -> tuple[Optional[object], Optional[str]]:
    db = _get_db()
    m = _get_models()
    milestone = db.session.get(m.Milestone, milestone_id)
    if not milestone:
        return None, f"Milestone {milestone_id} not found"
    _, error = require_project_access(ctx, milestone.project_id)
    if error:
        return None, error
    return milestone, None


def require_sprint_access(ctx, sprint_id: str) -> tuple[Optional[object], Optional[str]]:
    db = _get_db()
    m = _get_models()
    sprint = db.session.get(m.Sprint, sprint_id)
    if not sprint:
        return None, f"Sprint {sprint_id} not found"
    _, error = require_project_access(ctx, sprint.project_id)
    if error:
        return None, error
    return sprint, None


# ---------------------------------------------------------------------------
# READ / QUERY
# ---------------------------------------------------------------------------

def get_workspace_summary(workspace_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    error = require_workspace_access(_ctx(), workspace_id)
    if error:
        return _fail(error)

    workspace = db.session.get(m.Workspace, workspace_id)
    if not workspace:
        return _fail(f"Workspace {workspace_id} not found")

    companies = m.Company.query.filter_by(workspace_id=workspace_id).all()
    result = {
        "workspace": {"id": workspace.id, "name": workspace.name, "persona": workspace.persona},
        "initiatives": []
    }

    for c in companies:
        projects = m.Project.query.filter_by(company_id=c.id).all()
        c_data = {
            "id": c.id,
            "name": c.name,
            "mission": c.mission,
            "color": c.color,
            "projects": []
        }
        for p in projects:
            tasks = m.Task.query.filter_by(project_id=p.id).all()
            task_summary = {
                "total": len(tasks),
                "by_status": {},
                "high_priority": [],
                "in_progress": []
            }
            for t in tasks:
                task_summary["by_status"][t.status] = task_summary["by_status"].get(t.status, 0) + 1
                if t.priority in ("high", "critical"):
                    task_summary["high_priority"].append({"id": t.id, "title": t.title, "status": t.status})
                if t.status == "in-progress":
                    task_summary["in_progress"].append({"id": t.id, "title": t.title, "priority": t.priority})

            c_data["projects"].append({
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "progress": p.progress,
                "task_summary": task_summary
            })
        result["initiatives"].append(c_data)

    return _ok(result)


def list_workspace_members(workspace_id: str) -> dict:
    """Lists members of a workspace with id/name/email — used to resolve a person's name to
    a user id before assigning a task to them."""
    db = _get_db()
    m = _get_models()

    error = require_workspace_access(_ctx(), workspace_id)
    if error:
        return _fail(error)

    if not db.session.get(m.Workspace, workspace_id):
        return _fail(f"Workspace {workspace_id} not found")

    members = m.WorkspaceMember.query.filter_by(workspace_id=workspace_id).all()
    users = {u.id: u for u in m.User.query.filter(
        m.User.id.in_([mem.user_id for mem in members])
    ).all()} if members else {}

    return _ok([
        {"id": mem.user_id, "name": users[mem.user_id].name, "email": users[mem.user_id].email}
        for mem in members if mem.user_id in users
    ])


def get_tasks(workspace_id: str, project_id: Optional[str] = None,
              status: Optional[str] = None, priority: Optional[str] = None) -> dict:
    m = _get_models()
    ctx = _ctx()

    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    if project_id:
        project, error = require_project_access(ctx, project_id)
        if error:
            return _fail(error)
        if project.workspace_id != workspace_id:
            return _fail("Project is outside the requested workspace")

    q = m.Task.query.filter_by(workspace_id=workspace_id)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if priority:
        q = q.filter_by(priority=priority)

    tasks = q.all()
    return _ok([{
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "estimated_hours": t.estimated_hours,
        "is_daily_focus": t.is_daily_focus,
        "project_id": t.project_id
    } for t in tasks])


def analyze_workspace_progress(workspace_id: str) -> dict:
    m = _get_models()

    error = require_workspace_access(_ctx(), workspace_id)
    if error:
        return _fail(error)

    companies = m.Company.query.filter_by(workspace_id=workspace_id).all()
    analysis = {
        "total_tasks": 0,
        "completed": 0,
        "in_progress": 0,
        "overdue_high_priority": [],
        "stalled_projects": [],
        "completion_rate": 0,
        "suggested_focus": []
    }

    for c in companies:
        projects = m.Project.query.filter_by(company_id=c.id).all()
        for p in projects:
            tasks = m.Task.query.filter_by(project_id=p.id).all()
            if not tasks:
                continue

            done_count = sum(1 for t in tasks if t.status == "done")
            active_count = sum(1 for t in tasks if t.status not in ("done", "backlog"))

            analysis["total_tasks"] += len(tasks)
            analysis["completed"] += done_count
            analysis["in_progress"] += sum(1 for t in tasks if t.status == "in-progress")

            if active_count > 0 and done_count == 0:
                analysis["stalled_projects"].append({
                    "project": p.name,
                    "initiative": c.name,
                    "task_count": active_count
                })

            for t in tasks:
                if t.priority in ("high", "critical") and t.status in ("todo", "backlog"):
                    analysis["overdue_high_priority"].append({
                        "id": t.id,
                        "title": t.title,
                        "project": p.name,
                        "priority": t.priority
                    })

    if analysis["total_tasks"] > 0:
        analysis["completion_rate"] = round(
            (analysis["completed"] / analysis["total_tasks"]) * 100, 1
        )

    analysis["suggested_focus"] = analysis["overdue_high_priority"][:3]
    return _ok(analysis)


def get_projects(workspace_id: str) -> dict:
    m = _get_models()

    error = require_workspace_access(_ctx(), workspace_id)
    if error:
        return _fail(error)

    companies = m.Company.query.filter_by(workspace_id=workspace_id).all()
    projects = []
    for c in companies:
        for p in m.Project.query.filter_by(company_id=c.id).all():
            projects.append({
                "id": p.id,
                "name": p.name,
                "type": p.type,
                "mission": p.mission,
                "progress": p.progress,
                "initiative": c.name,
                "initiative_id": c.id
            })
    return _ok(projects)


def get_project_tasks(project_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    project, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)

    tasks = m.Task.query.filter_by(project_id=project_id).all()
    by_status: dict = {}
    for t in tasks:
        by_status.setdefault(t.status, []).append({
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "estimated_hours": t.estimated_hours
        })

    return _ok({
        "project_id": project_id,
        "project_name": project.name,
        "total_tasks": len(tasks),
        "by_status": by_status
    })


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

def create_task(
    project_id: str,
    workspace_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    estimated_hours: float = 1.0,
    status: str = "todo"
) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    project, error = require_project_access(ctx, project_id)
    if error:
        return _fail(error)
    if project.workspace_id != workspace_id:
        return _fail("Project is outside the requested workspace")
    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    if not title or not str(title).strip():
        return _fail("Task title is required")

    task = m.Task(
        id=str(uuid.uuid4()),
        project_id=project_id,
        workspace_id=workspace_id,
        title=str(title).strip(),
        description=description,
        priority=priority,
        estimated_hours=estimated_hours,
        status=status,
        is_daily_focus=False,
        resources=[]
    )
    db.session.add(task)
    db.session.commit()
    return _ok({"id": task.id, "title": task.title, "status": "created", "project_id": project_id})


def create_multiple_tasks(project_id: str, workspace_id: str, tasks: str) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    project, error = require_project_access(ctx, project_id)
    if error:
        return _fail(error)
    if project.workspace_id != workspace_id:
        return _fail("Project is outside the requested workspace")
    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)

    try:
        task_list = json.loads(tasks)
    except json.JSONDecodeError as e:
        return _fail(f"Invalid JSON for tasks: {e}")

    created = []
    for td in task_list:
        if not isinstance(td, dict):
            return _fail("Each task must be an object")
        if not td.get("title"):
            return _fail("Each task requires a title")
        task = m.Task(
            id=str(uuid.uuid4()),
            project_id=project_id,
            workspace_id=workspace_id,
            title=str(td.get("title")).strip(),
            description=td.get("description", ""),
            priority=td.get("priority", "medium"),
            estimated_hours=td.get("estimated_hours", 1.0),
            status=td.get("status", "todo"),
            is_daily_focus=False,
            resources=[]
        )
        db.session.add(task)
        created.append({"id": task.id, "title": task.title})

    db.session.commit()
    return _ok({"created_count": len(created), "tasks": created})


def create_project(
    initiative_id: str,
    workspace_id: str,
    name: str,
    project_type: str = "build",
    mission: str = ""
) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    initiative = db.session.get(m.Company, initiative_id)
    if not initiative:
        return _fail(f"Initiative {initiative_id} not found")
    if initiative.workspace_id != workspace_id:
        return _fail("Initiative is outside the requested workspace")
    if not name or not str(name).strip():
        return _fail("Project name is required")

    project = m.Project(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        company_id=initiative_id,
        name=str(name).strip(),
        type=project_type,
        mission=mission,
        progress=0,
        whiteboard=[]
    )
    db.session.add(project)
    db.session.commit()
    return _ok({"id": project.id, "name": project.name, "status": "created"})


def create_initiative(
    workspace_id: str,
    name: str,
    mission: str = "",
    color: str = "indigo"
) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    if not name or not str(name).strip():
        return _fail("Initiative name is required")

    initiative = m.Company(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=str(name).strip(),
        mission=mission,
        color=color,
        whiteboard=[]
    )
    db.session.add(initiative)
    db.session.commit()
    return _ok({"id": initiative.id, "name": initiative.name, "status": "created"})


def create_note(workspace_id: str, content: str, project_id: Optional[str] = None) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)
    if project_id:
        project, error = require_project_access(ctx, project_id)
        if error:
            return _fail(error)
        if project.workspace_id != workspace_id:
            return _fail("Project is outside the requested workspace")

    note = m.Note(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        context_id=project_id,
        content=content,
        type="general",
        color="white"
    )
    db.session.add(note)
    db.session.commit()
    return _ok({"id": note.id, "status": "created"})


def create_project_plan(project_id: str, workspace_id: str, plan: str) -> dict:
    db = _get_db()
    m = _get_models()
    ctx = _ctx()

    project, error = require_project_access(ctx, project_id)
    if error:
        return _fail(error)
    if project.workspace_id != workspace_id:
        return _fail("Project is outside the requested workspace")
    error = require_workspace_access(ctx, workspace_id)
    if error:
        return _fail(error)

    try:
        milestones = json.loads(plan)
    except json.JSONDecodeError as e:
        return _fail(f"Invalid plan JSON: {e}")

    if not isinstance(milestones, list):
        return _fail("Plan must be a list of milestone objects")

    created_tasks = []
    milestone_summary = []

    for order, milestone in enumerate(milestones):
        milestone_name = milestone.get("name", "Milestone")
        target_week = milestone.get("target_week", "")
        tasks = milestone.get("tasks", [])
        milestone_tasks = []

        milestone_row = m.Milestone(
            project_id=project_id,
            title=milestone_name,
            description=target_week,
            order=order,
        )
        db.session.add(milestone_row)
        db.session.flush()  # assign milestone_row.id before tasks reference it

        for td in tasks:
            task = m.Task(
                id=str(uuid.uuid4()),
                project_id=project_id,
                workspace_id=workspace_id,
                milestone_id=milestone_row.id,
                title=td.get("title", "Untitled Task"),
                description=td.get("description", ""),
                priority=td.get("priority", "medium"),
                estimated_hours=td.get("estimated_hours", 2.0),
                status=td.get("status", "todo"),
                is_daily_focus=False,
                resources=[]
            )
            db.session.add(task)
            milestone_tasks.append({"id": task.id, "title": task.title})
            created_tasks.append(task.id)

        milestone_summary.append({
            "milestone": milestone_name,
            "milestone_id": milestone_row.id,
            "target": target_week,
            "task_count": len(milestone_tasks),
            "tasks": milestone_tasks
        })

    db.session.commit()
    return _ok({
        "status": "created",
        "total_tasks": len(created_tasks),
        "milestone_count": len(milestones),
        "milestones": milestone_summary
    })


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

def update_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    estimated_hours: Optional[float] = None,
    is_daily_focus: Optional[bool] = None,
    assignee_id: Optional[str] = None,
) -> dict:
    db = _get_db()
    m = _get_models()

    task, error = require_task_access(_ctx(), task_id)
    if error:
        return _fail(error)

    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if status is not None:
        task.status = status
    if priority is not None:
        task.priority = priority
    if estimated_hours is not None:
        task.estimated_hours = estimated_hours
    if is_daily_focus is not None:
        task.is_daily_focus = is_daily_focus
    if assignee_id is not None:
        task.assignee_id = assignee_id

    db.session.commit()
    return _ok({"id": task.id, "title": task.title, "status": "updated"})


def update_task_status(task_id: str, new_status: str) -> dict:
    db = _get_db()
    m = _get_models()

    task, error = require_task_access(_ctx(), task_id)
    if error:
        return _fail(error)

    old_status = task.status
    task.status = new_status
    db.session.commit()
    return _ok({"id": task.id, "title": task.title, "old_status": old_status, "new_status": new_status})


def update_project(
    project_id: str,
    name: Optional[str] = None,
    mission: Optional[str] = None,
    progress: Optional[int] = None
) -> dict:
    db = _get_db()
    m = _get_models()

    project, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)

    if name is not None:
        project.name = name
    if mission is not None:
        project.mission = mission
    if progress is not None:
        project.progress = max(0, min(100, progress))

    db.session.commit()
    return _ok({"id": project.id, "name": project.name, "status": "updated"})


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

def delete_task(task_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    task, error = require_task_access(_ctx(), task_id)
    if error:
        return _fail(error)

    title = task.title
    db.session.delete(task)
    db.session.commit()
    return _ok({"deleted_task_id": task_id, "title": title, "status": "deleted"})


def delete_project(project_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    project, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)

    m.Task.query.filter_by(project_id=project_id).delete()
    name = project.name
    db.session.delete(project)
    db.session.commit()
    return _ok({"deleted_project_id": project_id, "name": name, "status": "deleted"})


# ---------------------------------------------------------------------------
# MILESTONES
# ---------------------------------------------------------------------------

def _milestone_dict(ms) -> dict:
    return {
        "id": ms.id, "projectId": ms.project_id, "title": ms.title,
        "description": ms.description,
        "dueDate": ms.due_date.isoformat() if ms.due_date else None,
        "status": ms.status, "order": ms.order,
    }


def list_milestones(project_id: str) -> dict:
    m = _get_models()
    _, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)
    milestones = m.Milestone.query.filter_by(project_id=project_id).order_by(m.Milestone.order).all()
    return _ok([_milestone_dict(ms) for ms in milestones])


def create_milestone(
    project_id: str, title: str, description: str = "",
    due_date: Optional[str] = None, order: int = 0
) -> dict:
    from datetime import datetime as _dt
    db = _get_db()
    m = _get_models()

    project, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)

    milestone = m.Milestone(
        project_id=project_id, title=title, description=description,
        due_date=_dt.fromisoformat(due_date) if due_date else None,
        order=order,
    )
    db.session.add(milestone)
    db.session.commit()
    return _ok(_milestone_dict(milestone))


def update_milestone(
    milestone_id: str, title: Optional[str] = None, description: Optional[str] = None,
    due_date: Optional[str] = None, status: Optional[str] = None, order: Optional[int] = None
) -> dict:
    from datetime import datetime as _dt
    db = _get_db()
    m = _get_models()

    milestone, error = require_milestone_access(_ctx(), milestone_id)
    if error:
        return _fail(error)

    if title is not None:
        milestone.title = title
    if description is not None:
        milestone.description = description
    if due_date is not None:
        milestone.due_date = _dt.fromisoformat(due_date) if due_date else None
    if status is not None:
        milestone.status = status
    if order is not None:
        milestone.order = order

    db.session.commit()
    return _ok(_milestone_dict(milestone))


def delete_milestone(milestone_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    milestone, error = require_milestone_access(_ctx(), milestone_id)
    if error:
        return _fail(error)

    m.Task.query.filter_by(milestone_id=milestone_id).update({"milestone_id": None})
    title = milestone.title
    db.session.delete(milestone)
    db.session.commit()
    return _ok({"deleted_milestone_id": milestone_id, "title": title, "status": "deleted"})


# ---------------------------------------------------------------------------
# SPRINTS
# ---------------------------------------------------------------------------

def _sprint_dict(sp) -> dict:
    return {
        "id": sp.id, "projectId": sp.project_id, "name": sp.name,
        "startDate": sp.start_date.isoformat() if sp.start_date else None,
        "endDate": sp.end_date.isoformat() if sp.end_date else None,
        "status": sp.status,
    }


def list_sprints(project_id: str) -> dict:
    m = _get_models()
    _, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)
    sprints = m.Sprint.query.filter_by(project_id=project_id).order_by(m.Sprint.created_at).all()
    return _ok([_sprint_dict(sp) for sp in sprints])


def create_sprint(
    project_id: str, name: str, start_date: Optional[str] = None,
    end_date: Optional[str] = None, status: str = "planned"
) -> dict:
    from datetime import datetime as _dt
    db = _get_db()
    m = _get_models()

    project, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)

    sprint = m.Sprint(
        project_id=project_id, name=name,
        start_date=_dt.fromisoformat(start_date) if start_date else None,
        end_date=_dt.fromisoformat(end_date) if end_date else None,
        status=status,
    )
    db.session.add(sprint)
    db.session.commit()
    return _ok(_sprint_dict(sprint))


def update_sprint(
    sprint_id: str, name: Optional[str] = None, start_date: Optional[str] = None,
    end_date: Optional[str] = None, status: Optional[str] = None
) -> dict:
    from datetime import datetime as _dt
    db = _get_db()
    m = _get_models()

    sprint, error = require_sprint_access(_ctx(), sprint_id)
    if error:
        return _fail(error)

    if name is not None:
        sprint.name = name
    if start_date is not None:
        sprint.start_date = _dt.fromisoformat(start_date) if start_date else None
    if end_date is not None:
        sprint.end_date = _dt.fromisoformat(end_date) if end_date else None
    if status is not None:
        sprint.status = status

    db.session.commit()
    return _ok(_sprint_dict(sprint))


def delete_sprint(sprint_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    sprint, error = require_sprint_access(_ctx(), sprint_id)
    if error:
        return _fail(error)

    m.Task.query.filter_by(sprint_id=sprint_id).update({"sprint_id": None})
    name = sprint.name
    db.session.delete(sprint)
    db.session.commit()
    return _ok({"deleted_sprint_id": sprint_id, "name": name, "status": "deleted"})


# ---------------------------------------------------------------------------
# TASK DEPENDENCIES
# ---------------------------------------------------------------------------

def _dependency_dict(dep) -> dict:
    return {
        "id": dep.id, "taskId": dep.task_id, "dependsOnTaskId": dep.depends_on_task_id,
        "type": dep.type,
    }


def _has_path(m, start_task_id: str, target_task_id: str) -> bool:
    """DFS over 'depends_on' edges: is target_task_id reachable from start_task_id?"""
    visited = set()
    stack = [start_task_id]
    while stack:
        current = stack.pop()
        if current == target_task_id:
            return True
        if current in visited:
            continue
        visited.add(current)
        edges = m.TaskDependency.query.filter_by(task_id=current).all()
        stack.extend(e.depends_on_task_id for e in edges)
    return False


def add_task_dependency(task_id: str, depends_on_task_id: str, dependency_type: str = "blocks") -> dict:
    db = _get_db()
    m = _get_models()

    if task_id == depends_on_task_id:
        return _fail("A task cannot depend on itself")

    ctx = _ctx()
    task, error = require_task_access(ctx, task_id)
    if error:
        return _fail(error)
    depends_on, error = require_task_access(ctx, depends_on_task_id)
    if error:
        return _fail(error)
    if task.workspace_id != depends_on.workspace_id:
        return _fail("Dependency tasks must be in the same workspace")

    # Adding task_id -> depends_on_task_id would create a cycle if depends_on_task_id
    # can already (transitively) reach task_id via existing 'depends_on' edges.
    if _has_path(m, depends_on_task_id, task_id):
        return _fail("This dependency would create a cycle")

    existing = m.TaskDependency.query.filter_by(
        task_id=task_id, depends_on_task_id=depends_on_task_id, type=dependency_type
    ).first()
    if existing:
        return _fail("This dependency already exists")

    dep = m.TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id, type=dependency_type)
    db.session.add(dep)
    db.session.commit()
    return _ok(_dependency_dict(dep))


def remove_task_dependency(dependency_id: str) -> dict:
    db = _get_db()
    m = _get_models()

    dep = db.session.get(m.TaskDependency, dependency_id)
    if not dep:
        return _fail(f"Dependency {dependency_id} not found")
    _, error = require_task_access(_ctx(), dep.task_id)
    if error:
        return _fail(error)

    db.session.delete(dep)
    db.session.commit()
    return _ok({"deleted_dependency_id": dependency_id, "status": "deleted"})


def get_task_dependencies(task_id: str) -> dict:
    m = _get_models()
    _, error = require_task_access(_ctx(), task_id)
    if error:
        return _fail(error)

    blocks = m.TaskDependency.query.filter_by(task_id=task_id).all()
    blocked_by = m.TaskDependency.query.filter_by(depends_on_task_id=task_id).all()

    def _related(dep, other_id):
        other = m.Task.query.get(other_id)
        return {
            "dependencyId": dep.id, "type": dep.type,
            "task": {"id": other.id, "title": other.title, "status": other.status} if other else None,
        }

    return _ok({
        "dependsOn": [_related(d, d.depends_on_task_id) for d in blocks],
        "blockedBy": [_related(d, d.task_id) for d in blocked_by],
    })


def get_blocked_tasks(project_id: str) -> dict:
    m = _get_models()
    _, error = require_project_access(_ctx(), project_id)
    if error:
        return _fail(error)

    tasks = {t.id: t for t in m.Task.query.filter_by(project_id=project_id).all()}
    deps = m.TaskDependency.query.filter(m.TaskDependency.task_id.in_(tasks.keys())).all()

    blocked = {}
    for dep in deps:
        blocker = tasks.get(dep.depends_on_task_id) or m.Task.query.get(dep.depends_on_task_id)
        if blocker and blocker.status != "done":
            blocked.setdefault(dep.task_id, []).append({
                "id": blocker.id, "title": blocker.title, "status": blocker.status,
            })

    return _ok([
        {"taskId": task_id, "blockedByTasks": blockers}
        for task_id, blockers in blocked.items()
    ])


# ---------------------------------------------------------------------------
# AI REPLANNING — reuses the Core Intelligence Layer's recursive
# planner -> executor -> reflect loop (graph_v2.py), scoped to an existing project.
# ---------------------------------------------------------------------------

def replan_project(project_id: str, workspace_id: str, user_id: str, goal: str) -> dict:
    import uuid as _uuid
    from langchain_core.messages import HumanMessage
    from ..agents.graph_v2 import create_orchestrator

    db = _get_db()
    m = _get_models()

    project = db.session.get(m.Project, project_id)
    if not project:
        return _fail(f"Project {project_id} not found")
    error = require_workspace_access(_ctx(), workspace_id)
    if error:
        return _fail(error)
    if project.workspace_id != workspace_id:
        return _fail("Project is outside the requested workspace")

    prompt = (
        f"Replan project '{project.name}' (project_id={project_id}): {goal}. "
        "Use the project management tools (milestones, sprints, tasks, dependencies) "
        "to make the necessary changes directly — don't just describe a plan, execute it."
    )

    orchestrator = create_orchestrator()
    thread_id = f"replan_{project_id}_{_uuid.uuid4()}"
    initial_state = {
        "messages": [HumanMessage(content=prompt)],
        "workspace_id": workspace_id,
        "user_id": user_id,
        "workspace_context": {},
        "complexity": None,
        "goal": None,
        "plan": [],
        "working_memory": {},
        "current_step_index": 0,
        "replan_count": 0,
        "next_action": None,
        "final_answer": None,
        "planning_phase": None,
        "draft_plan": {},
        "planning_project_id": None,
    }
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

    try:
        result = orchestrator.invoke(initial_state, config=config)
    except Exception as e:
        return _fail(f"Replan failed: {e}")

    steps = [
        {"description": s.get("description"), "status": s.get("status"), "result": s.get("result")}
        for s in result.get("plan", [])
    ]
    summary = result.get("final_answer")
    if not summary:
        last_msg = result["messages"][-1] if result.get("messages") else None
        summary = getattr(last_msg, "content", None) or "Replan complete."

    return _ok({"summary": summary, "steps": steps})
