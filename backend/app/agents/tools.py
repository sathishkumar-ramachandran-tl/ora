"""
LangChain tool definitions for the Sindhai Agentic System.

CRUD tools mutate data directly via SQLAlchemy (same DB session).
Read tools query safely without modification.
All tools run inside Flask application context.
"""
import uuid
import json
from typing import Optional
from langchain_core.tools import tool
from sqlalchemy import text


# ---------------------------------------------------------------------------
# Lazy DB import — avoids circular import at module load time
# ---------------------------------------------------------------------------
def _get_db():
    from ..extensions import db
    return db

def _get_models():
    from .. import models
    return models


# ---------------------------------------------------------------------------
# READ / QUERY TOOLS
# ---------------------------------------------------------------------------

@tool
def get_workspace_summary(workspace_id: str) -> dict:
    """
    Get a full summary of the workspace including all initiatives, projects and tasks.
    Use this to answer questions about what's going on in the user's workspace.
    """
    db = _get_db()
    m = _get_models()

    workspace = db.session.get(m.Workspace, workspace_id)
    if not workspace:
        return {"error": f"Workspace {workspace_id} not found"}

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

    return result


@tool
def get_tasks(workspace_id: str, project_id: Optional[str] = None,
              status: Optional[str] = None, priority: Optional[str] = None) -> list:
    """
    List tasks in the workspace, optionally filtered by project, status, or priority.
    Status options: todo, in-progress, review, done, backlog.
    Priority options: low, medium, high, critical.
    """
    db = _get_db()
    m = _get_models()

    q = m.Task.query.filter_by(workspace_id=workspace_id)
    if project_id:
        q = q.filter_by(project_id=project_id)
    if status:
        q = q.filter_by(status=status)
    if priority:
        q = q.filter_by(priority=priority)

    tasks = q.all()
    return [{
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "estimated_hours": t.estimated_hours,
        "is_daily_focus": t.is_daily_focus,
        "project_id": t.project_id
    } for t in tasks]


@tool
def analyze_workspace_progress(workspace_id: str) -> dict:
    """
    Analyze workspace progress metrics: completion rates, overloaded projects,
    stalled tasks, and suggested priorities. Returns an analysis object.
    """
    db = _get_db()
    m = _get_models()

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

    # Suggest top 3 focus items
    analysis["suggested_focus"] = analysis["overdue_high_priority"][:3]
    return analysis


@tool
def get_projects(workspace_id: str) -> list:
    """List all projects in the workspace with their initiative context."""
    db = _get_db()
    m = _get_models()

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
    return projects


# ---------------------------------------------------------------------------
# CRUD TOOLS — CREATE
# ---------------------------------------------------------------------------

@tool
def create_task(
    project_id: str,
    workspace_id: str,
    title: str,
    description: str = "",
    priority: str = "medium",
    estimated_hours: float = 1.0,
    status: str = "todo"
) -> dict:
    """
    Create a new task inside a project.
    priority must be one of: low, medium, high, critical.
    status must be one of: backlog, todo, in-progress, review, done.
    Returns the created task id.
    """
    db = _get_db()
    m = _get_models()

    task = m.Task(
        id=str(uuid.uuid4()),
        project_id=project_id,
        workspace_id=workspace_id,
        title=title,
        description=description,
        priority=priority,
        estimated_hours=estimated_hours,
        status=status,
        is_daily_focus=False,
        resources=[]
    )
    db.session.add(task)
    db.session.commit()
    return {"id": task.id, "title": task.title, "status": "created", "project_id": project_id}


@tool
def create_multiple_tasks(project_id: str, workspace_id: str, tasks: str) -> dict:
    """
    Create multiple tasks at once. 'tasks' must be a JSON string: a list of objects
    each with: title (required), description, priority, estimated_hours, status.
    Example: '[{"title":"Setup CI","priority":"high","estimated_hours":2}]'
    Returns count of tasks created and their IDs.
    """
    db = _get_db()
    m = _get_models()

    try:
        task_list = json.loads(tasks)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON for tasks: {e}"}

    created = []
    for td in task_list:
        task = m.Task(
            id=str(uuid.uuid4()),
            project_id=project_id,
            workspace_id=workspace_id,
            title=td.get("title", "Untitled Task"),
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
    return {"created_count": len(created), "tasks": created}


@tool
def create_project(
    initiative_id: str,
    workspace_id: str,
    name: str,
    project_type: str = "build",
    mission: str = ""
) -> dict:
    """
    Create a new project under an initiative.
    project_type: build | learning | research | client | campaign.
    Returns the new project id.
    """
    db = _get_db()
    m = _get_models()

    project = m.Project(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        company_id=initiative_id,
        name=name,
        type=project_type,
        mission=mission,
        progress=0,
        whiteboard=[]
    )
    db.session.add(project)
    db.session.commit()
    return {"id": project.id, "name": project.name, "status": "created"}


@tool
def create_initiative(
    workspace_id: str,
    name: str,
    mission: str = "",
    color: str = "indigo"
) -> dict:
    """
    Create a new initiative (top-level grouping for projects).
    color options: indigo, emerald, amber, rose, slate, purple, blue.
    Returns the new initiative id.
    """
    db = _get_db()
    m = _get_models()

    initiative = m.Company(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        name=name,
        mission=mission,
        color=color,
        whiteboard=[]
    )
    db.session.add(initiative)
    db.session.commit()
    return {"id": initiative.id, "name": initiative.name, "status": "created"}


# ---------------------------------------------------------------------------
# CRUD TOOLS — UPDATE
# ---------------------------------------------------------------------------

@tool
def update_task(
    task_id: str,
    title: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    estimated_hours: Optional[float] = None,
    is_daily_focus: Optional[bool] = None
) -> dict:
    """
    Update fields of an existing task. Only pass fields you want to change.
    status options: backlog, todo, in-progress, review, done.
    priority options: low, medium, high, critical.
    """
    db = _get_db()
    m = _get_models()

    task = db.session.get(m.Task, task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

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

    db.session.commit()
    return {"id": task.id, "title": task.title, "status": "updated"}


@tool
def update_task_status(task_id: str, new_status: str) -> dict:
    """
    Move a task to a new status column.
    new_status: backlog | todo | in-progress | review | done
    """
    db = _get_db()
    m = _get_models()

    task = db.session.get(m.Task, task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    old_status = task.status
    task.status = new_status
    db.session.commit()
    return {"id": task.id, "title": task.title, "old_status": old_status, "new_status": new_status}


@tool
def update_project(
    project_id: str,
    name: Optional[str] = None,
    mission: Optional[str] = None,
    progress: Optional[int] = None
) -> dict:
    """Update a project's name, mission, or progress percentage (0-100)."""
    db = _get_db()
    m = _get_models()

    project = db.session.get(m.Project, project_id)
    if not project:
        return {"error": f"Project {project_id} not found"}

    if name is not None:
        project.name = name
    if mission is not None:
        project.mission = mission
    if progress is not None:
        project.progress = max(0, min(100, progress))

    db.session.commit()
    return {"id": project.id, "name": project.name, "status": "updated"}


# ---------------------------------------------------------------------------
# CRUD TOOLS — DELETE
# ---------------------------------------------------------------------------

@tool
def delete_task(task_id: str) -> dict:
    """Permanently delete a task. This cannot be undone."""
    db = _get_db()
    m = _get_models()

    task = db.session.get(m.Task, task_id)
    if not task:
        return {"error": f"Task {task_id} not found"}

    title = task.title
    db.session.delete(task)
    db.session.commit()
    return {"deleted_task_id": task_id, "title": title, "status": "deleted"}


@tool
def delete_project(project_id: str) -> dict:
    """Permanently delete a project and all its tasks. This cannot be undone."""
    db = _get_db()
    m = _get_models()

    project = db.session.get(m.Project, project_id)
    if not project:
        return {"error": f"Project {project_id} not found"}

    # Delete all tasks first
    m.Task.query.filter_by(project_id=project_id).delete()
    name = project.name
    db.session.delete(project)
    db.session.commit()
    return {"deleted_project_id": project_id, "name": name, "status": "deleted"}


# ---------------------------------------------------------------------------
# PLANNING TOOLS — structured milestone-based plan creation
# ---------------------------------------------------------------------------

@tool
def create_project_plan(project_id: str, workspace_id: str, plan: str) -> dict:
    """
    Create a complete milestone-based project plan atomically.

    'plan' must be a JSON string — a list of milestone objects:
    [
      {
        "name": "Milestone name",
        "target_week": "Week 2",
        "tasks": [
          {"title": "Task title", "description": "...", "priority": "high", "estimated_hours": 4.0}
        ]
      }
    ]
    Priority: low | medium | high | critical.
    The milestone name is embedded into each task's description for board context.
    Returns a summary of what was created.
    """
    db = _get_db()
    m = _get_models()

    try:
        milestones = json.loads(plan)
    except json.JSONDecodeError as e:
        return {"error": f"Invalid plan JSON: {e}"}

    if not isinstance(milestones, list):
        return {"error": "Plan must be a list of milestone objects"}

    created_tasks = []
    milestone_summary = []

    for milestone in milestones:
        milestone_name = milestone.get("name", "Milestone")
        target_week = milestone.get("target_week", "")
        tasks = milestone.get("tasks", [])
        milestone_tasks = []

        for td in tasks:
            description = td.get("description", "")
            milestone_tag = f"[{milestone_name}]" + (f" [{target_week}]" if target_week else "")
            full_desc = f"{milestone_tag} {description}".strip()

            task = m.Task(
                id=str(uuid.uuid4()),
                project_id=project_id,
                workspace_id=workspace_id,
                title=td.get("title", "Untitled Task"),
                description=full_desc,
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
            "target": target_week,
            "task_count": len(milestone_tasks),
            "tasks": milestone_tasks
        })

    db.session.commit()
    return {
        "status": "created",
        "total_tasks": len(created_tasks),
        "milestone_count": len(milestones),
        "milestones": milestone_summary
    }


@tool
def get_project_tasks(project_id: str) -> dict:
    """
    Get all tasks for a specific project, grouped by status.
    Use during planning to understand what already exists before adding more.
    """
    db = _get_db()
    m = _get_models()

    project = db.session.get(m.Project, project_id)
    if not project:
        return {"error": f"Project {project_id} not found"}

    tasks = m.Task.query.filter_by(project_id=project_id).all()
    by_status: dict = {}
    for t in tasks:
        by_status.setdefault(t.status, []).append({
            "id": t.id,
            "title": t.title,
            "priority": t.priority,
            "estimated_hours": t.estimated_hours
        })

    return {
        "project_id": project_id,
        "project_name": project.name,
        "total_tasks": len(tasks),
        "by_status": by_status
    }


# ---------------------------------------------------------------------------
# NOTE / CALENDAR TOOLS
# ---------------------------------------------------------------------------

@tool
def create_note(workspace_id: str, content: str, project_id: Optional[str] = None) -> dict:
    """Create a note in the workspace, optionally linked to a project."""
    db = _get_db()
    m = _get_models()

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
    return {"id": note.id, "status": "created"}


# ---------------------------------------------------------------------------
# Tool registries by agent role
# ---------------------------------------------------------------------------

READ_TOOLS = [get_workspace_summary, get_tasks, analyze_workspace_progress, get_projects]

CRUD_TOOLS = [
    create_task, create_multiple_tasks, create_project, create_initiative,
    update_task, update_task_status, update_project,
    delete_task, delete_project,
    create_note
]

PLANNING_TOOLS = [
    get_workspace_summary, get_projects, get_project_tasks,
    create_project_plan, create_multiple_tasks, create_project, create_initiative
]

ALL_TOOLS = list({t.name: t for t in READ_TOOLS + CRUD_TOOLS}.values())
