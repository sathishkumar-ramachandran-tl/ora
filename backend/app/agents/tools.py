"""
LangChain tool definitions for the Ora Agentic System.

Thin @tool wrappers around the shared business logic in app/tools/task_tools.py —
the same functions the MCP server (app/mcp_server.py) calls directly. Keeping the
implementation in one place means the in-process orchestrator and external MCP
clients can never drift out of sync on what a given tool actually does.

All tools run inside Flask application context.
"""
from datetime import datetime
from typing import Optional
from langchain_core.tools import tool

from ..tools import task_tools, calendar_tools, module_tools


def _unwrap(result: dict):
    """Convert the shared {success, data, error} shape into what the LLM prompts expect:
    the data payload on success, or {"error": ...} on failure (matches pre-refactor behavior)."""
    if result["success"]:
        return result["data"]
    return {"error": result["error"]}


# ---------------------------------------------------------------------------
# READ / QUERY TOOLS
# ---------------------------------------------------------------------------

@tool
def get_workspace_summary(workspace_id: str) -> dict:
    """
    Get a full summary of the workspace including all initiatives, projects and tasks.
    Use this to answer questions about what's going on in the user's workspace.
    """
    return _unwrap(task_tools.get_workspace_summary(workspace_id))


@tool
def list_workspace_members(workspace_id: str) -> dict:
    """
    List the people (id, name, email) who are members of this workspace. Call this first
    when a user asks to assign a task to someone by name, so you can resolve their name to
    a user id before calling update_task with assignee_id.
    """
    return _unwrap(task_tools.list_workspace_members(workspace_id))


@tool
def get_tasks(workspace_id: str, project_id: Optional[str] = None,
              status: Optional[str] = None, priority: Optional[str] = None) -> list:
    """
    List tasks in the workspace, optionally filtered by project, status, or priority.
    Status options: todo, in-progress, review, done, backlog.
    Priority options: low, medium, high, critical.
    """
    return _unwrap(task_tools.get_tasks(workspace_id, project_id, status, priority))


@tool
def analyze_workspace_progress(workspace_id: str) -> dict:
    """
    Analyze workspace progress metrics: completion rates, overloaded projects,
    stalled tasks, and suggested priorities. Returns an analysis object.
    """
    return _unwrap(task_tools.analyze_workspace_progress(workspace_id))


@tool
def get_projects(workspace_id: str) -> list:
    """List all projects in the workspace with their initiative context."""
    return _unwrap(task_tools.get_projects(workspace_id))


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
    return _unwrap(task_tools.create_task(project_id, workspace_id, title, description, priority, estimated_hours, status))


@tool
def create_multiple_tasks(project_id: str, workspace_id: str, tasks: str) -> dict:
    """
    Create multiple tasks at once. 'tasks' must be a JSON string: a list of objects
    each with: title (required), description, priority, estimated_hours, status.
    Example: '[{"title":"Setup CI","priority":"high","estimated_hours":2}]'
    Returns count of tasks created and their IDs.
    """
    return _unwrap(task_tools.create_multiple_tasks(project_id, workspace_id, tasks))


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
    return _unwrap(task_tools.create_project(initiative_id, workspace_id, name, project_type, mission))


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
    return _unwrap(task_tools.create_initiative(workspace_id, name, mission, color))


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
    is_daily_focus: Optional[bool] = None,
    assignee_id: Optional[str] = None,
) -> dict:
    """
    Update fields of an existing task. Only pass fields you want to change.
    status options: backlog, todo, in-progress, review, done.
    priority options: low, medium, high, critical.
    assignee_id: the user id to assign this task to a team member — use this for requests
    like "assign this task to <person>". Look up the user id from workspace members if you
    only have a name.
    """
    return _unwrap(task_tools.update_task(
        task_id, title, description, status, priority, estimated_hours, is_daily_focus, assignee_id
    ))


@tool
def update_task_status(task_id: str, new_status: str) -> dict:
    """
    Move a task to a new status column.
    new_status: backlog | todo | in-progress | review | done
    """
    return _unwrap(task_tools.update_task_status(task_id, new_status))


@tool
def update_project(
    project_id: str,
    name: Optional[str] = None,
    mission: Optional[str] = None,
    progress: Optional[int] = None
) -> dict:
    """Update a project's name, mission, or progress percentage (0-100)."""
    return _unwrap(task_tools.update_project(project_id, name, mission, progress))


# ---------------------------------------------------------------------------
# CRUD TOOLS — DELETE
# ---------------------------------------------------------------------------

@tool
def delete_task(task_id: str) -> dict:
    """Permanently delete a task. This cannot be undone."""
    return _unwrap(task_tools.delete_task(task_id))


@tool
def delete_project(project_id: str) -> dict:
    """Permanently delete a project and all its tasks. This cannot be undone."""
    return _unwrap(task_tools.delete_project(project_id))


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
    return _unwrap(task_tools.create_project_plan(project_id, workspace_id, plan))


@tool
def get_project_tasks(project_id: str) -> dict:
    """
    Get all tasks for a specific project, grouped by status.
    Use during planning to understand what already exists before adding more.
    """
    return _unwrap(task_tools.get_project_tasks(project_id))


# ---------------------------------------------------------------------------
# NOTE TOOLS
# ---------------------------------------------------------------------------

@tool
def create_note(workspace_id: str, content: str, project_id: Optional[str] = None) -> dict:
    """Create a note in the workspace, optionally linked to a project."""
    return _unwrap(task_tools.create_note(workspace_id, content, project_id))


# ---------------------------------------------------------------------------
# CALENDAR TOOLS
# ---------------------------------------------------------------------------

@tool
def list_calendar_events(workspace_id: str, user_id: str, start: str, end: str, scope: Optional[str] = None) -> dict:
    """
    List calendar events in an ISO 8601 [start, end) window, with recurring events
    expanded into concrete occurrences. scope: personal | workspace | company (optional —
    omit to see everything visible to the user).
    """
    return _unwrap(calendar_tools.list_events(
        workspace_id, user_id, datetime.fromisoformat(start), datetime.fromisoformat(end), scope
    ))


@tool
def create_calendar_event(
    workspace_id: str, owner_id: str, title: str, start: str, end: str,
    event_type: str = "personal", scope: str = "personal", color: str = "blue",
    timezone: str = "UTC", recurrence_rule: Optional[str] = None, attendees: Optional[list] = None
) -> dict:
    """
    Create a calendar event. start/end are ISO 8601 datetimes.
    event_type: task_block | meeting | personal | reminder.
    scope: personal | workspace | company — controls who else can see it.
    recurrence_rule: RFC5545 RRULE text, e.g. 'FREQ=WEEKLY;BYDAY=MO,WE,FR' (optional).
    attendees: user IDs, beyond the owner, who can see this event (optional).
    """
    return _unwrap(calendar_tools.create_event(
        workspace_id, owner_id, title, datetime.fromisoformat(start), datetime.fromisoformat(end),
        event_type, scope, None, color, timezone, recurrence_rule, attendees
    ))


@tool
def update_calendar_event(
    event_id: str, title: Optional[str] = None, start: Optional[str] = None,
    end: Optional[str] = None, color: Optional[str] = None, scope: Optional[str] = None
) -> dict:
    """Update fields of an existing calendar event. Only pass fields you want to change."""
    return _unwrap(calendar_tools.update_event(
        event_id, title,
        datetime.fromisoformat(start) if start else None,
        datetime.fromisoformat(end) if end else None,
        color, scope
    ))


@tool
def delete_calendar_event(event_id: str, delete_series: bool = False) -> dict:
    """Permanently delete a calendar event. This cannot be undone. Set delete_series=true to delete the whole recurring series."""
    return _unwrap(calendar_tools.delete_event(event_id, delete_series))


@tool
def find_availability(
    workspace_id: str, attendee_user_ids: list, duration_minutes: int,
    window_start: str, window_end: str, day_start_hour: int = 9, day_end_hour: int = 18
) -> dict:
    """
    Scan attendees' calendars for open slots within working hours. Use this before
    scheduling a meeting or focus block instead of guessing a free time. Returns up
    to 10 candidate slots.
    """
    return _unwrap(calendar_tools.find_availability(
        workspace_id, attendee_user_ids, duration_minutes,
        datetime.fromisoformat(window_start), datetime.fromisoformat(window_end),
        day_start_hour, day_end_hour
    ))


@tool
def auto_schedule_tasks(
    workspace_id: str, user_id: str, task_ids: Optional[list] = None,
    day_start_hour: int = 9, day_end_hour: int = 18, weekdays_only: bool = True,
    target_end_date: Optional[str] = None, block_hours: Optional[float] = None,
) -> dict:
    """
    Auto-schedule tasks into real free calendar slots (never invents a schedule — every
    block comes from find_availability, so it respects existing events). Without task_ids,
    schedules every open (non-done, not-yet-scheduled) task in the workspace, highest
    priority first. target_end_date (ISO date) caps how far out it will look; defaults to
    14 days out.
    """
    return _unwrap(calendar_tools.auto_schedule_tasks(
        workspace_id, user_id, task_ids=task_ids,
        day_start_hour=day_start_hour, day_end_hour=day_end_hour, weekdays_only=weekdays_only,
        window_end=target_end_date, block_hours=block_hours,
    ))


@tool
def schedule_module_milestones(module_instance_id: str, workspace_id: str, user_id: str, block_hours: float = 2.0) -> dict:
    """
    Read an installed module's milestones and auto-create task_block focus events for them,
    placed via find_availability so they land in genuinely free time near each milestone's
    due date.
    """
    return _unwrap(calendar_tools.schedule_module_milestones(module_instance_id, workspace_id, user_id, block_hours))


# ---------------------------------------------------------------------------
# MODULE MARKETPLACE TOOLS
# ---------------------------------------------------------------------------

@tool
def list_modules(category: Optional[str] = None) -> dict:
    """Browse published marketplace modules (pre-built learning/execution plans), optionally filtered by category: exam_prep | course | project | habit | general."""
    return _unwrap(module_tools.list_modules(category=category))


@tool
def generate_module(
    workspace_id: str, owner_id: str, goal: str, title: Optional[str] = None,
    category: str = "general", difficulty: str = "intermediate"
) -> dict:
    """
    Kick off AI generation of a brand-new module (a multi-milestone learning or execution
    plan) for a goal, e.g. "UPSC prep in 8 months" or "ship a personal portfolio site".
    Runs asynchronously — returns a moduleTemplateId immediately with status='pending'.
    Poll get_module_progress until status='ready', then call install_module.
    difficulty: beginner | intermediate | advanced.
    """
    from flask import current_app
    draft = module_tools.create_module_draft(
        title=title or goal[:80], description=goal, category=category,
        difficulty=difficulty, author_id=owner_id,
    )
    if draft["success"]:
        module_tools.start_generation(
            current_app._get_current_object(),
            module_template_id=draft["data"]["moduleTemplateId"],
            module_template_version_id=draft["data"]["moduleTemplateVersionId"],
            goal=goal, category=category, difficulty=difficulty,
        )
    return _unwrap(draft)


@tool
def get_module_progress(module_template_id: str) -> dict:
    """Check generation status for a module template: pending | generating | ready | failed."""
    return _unwrap(module_tools.get_generation_progress_by_template(module_template_id))


@tool
def install_module(module_template_id: str, workspace_id: str, owner_id: str) -> dict:
    """Install a ready (status='ready') module into the workspace — creates a real project with milestones and tasks."""
    return _unwrap(module_tools.install_module(module_template_id, workspace_id, owner_id))


# ---------------------------------------------------------------------------
# PROJECT MANAGEMENT TOOLS — milestones, sprints, dependencies (Phase 3)
# ---------------------------------------------------------------------------

@tool
def list_milestones(project_id: str) -> dict:
    """List milestones for a project, ordered by their sequence."""
    return _unwrap(task_tools.list_milestones(project_id))


@tool
def create_milestone(project_id: str, title: str, description: str = "", due_date: Optional[str] = None, order: int = 0) -> dict:
    """Create a milestone under a project. due_date is an ISO 8601 date/datetime string (optional)."""
    return _unwrap(task_tools.create_milestone(project_id, title, description, due_date, order))


@tool
def update_milestone(
    milestone_id: str, title: Optional[str] = None, description: Optional[str] = None,
    due_date: Optional[str] = None, status: Optional[str] = None, order: Optional[int] = None
) -> dict:
    """Update a milestone. status: pending | in_progress | done. Only pass fields you want to change."""
    return _unwrap(task_tools.update_milestone(milestone_id, title, description, due_date, status, order))


@tool
def delete_milestone(milestone_id: str) -> dict:
    """Delete a milestone. Tasks linked to it are unlinked (not deleted)."""
    return _unwrap(task_tools.delete_milestone(milestone_id))


@tool
def list_sprints(project_id: str) -> dict:
    """List sprints for a project."""
    return _unwrap(task_tools.list_sprints(project_id))


@tool
def create_sprint(project_id: str, name: str, start_date: Optional[str] = None, end_date: Optional[str] = None, status: str = "planned") -> dict:
    """Create a sprint under a project. status: planned | active | completed."""
    return _unwrap(task_tools.create_sprint(project_id, name, start_date, end_date, status))


@tool
def update_sprint(
    sprint_id: str, name: Optional[str] = None, start_date: Optional[str] = None,
    end_date: Optional[str] = None, status: Optional[str] = None
) -> dict:
    """Update a sprint. status: planned | active | completed. Only pass fields you want to change."""
    return _unwrap(task_tools.update_sprint(sprint_id, name, start_date, end_date, status))


@tool
def delete_sprint(sprint_id: str) -> dict:
    """Delete a sprint. Tasks linked to it are unlinked (not deleted)."""
    return _unwrap(task_tools.delete_sprint(sprint_id))


@tool
def add_task_dependency(task_id: str, depends_on_task_id: str, dependency_type: str = "blocks") -> dict:
    """
    Declare that task_id depends on depends_on_task_id (task_id is blocked until the
    other task is done). Rejected if it would create a dependency cycle.
    dependency_type: blocks | blocked_by | relates_to.
    """
    return _unwrap(task_tools.add_task_dependency(task_id, depends_on_task_id, dependency_type))


@tool
def remove_task_dependency(dependency_id: str) -> dict:
    """Remove a task dependency link."""
    return _unwrap(task_tools.remove_task_dependency(dependency_id))


@tool
def get_task_dependencies(task_id: str) -> dict:
    """Get what a task depends on and what depends on it."""
    return _unwrap(task_tools.get_task_dependencies(task_id))


@tool
def get_blocked_tasks(project_id: str) -> dict:
    """List tasks in a project that are currently blocked by an incomplete dependency."""
    return _unwrap(task_tools.get_blocked_tasks(project_id))


# ---------------------------------------------------------------------------
# Tool registries by agent role
# ---------------------------------------------------------------------------

READ_TOOLS = [get_workspace_summary, get_tasks, analyze_workspace_progress, get_projects, list_workspace_members]

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

CALENDAR_TOOLS = [
    list_calendar_events, create_calendar_event, update_calendar_event,
    delete_calendar_event, find_availability, auto_schedule_tasks, schedule_module_milestones,
]

MODULE_TOOLS = [list_modules, generate_module, get_module_progress, install_module]

# Milestones/sprints/dependencies. Deliberately excludes replan_project (task_tools.py) —
# that invokes the Core Intelligence Layer's own compiled graph, so it must only be
# reachable via the dedicated /projects/<id>/replan route and MCP tool, never as a tool
# an executor_node could call on itself mid-run.
PM_TOOLS = [
    list_milestones, create_milestone, update_milestone, delete_milestone,
    list_sprints, create_sprint, update_sprint, delete_sprint,
    add_task_dependency, remove_task_dependency, get_task_dependencies, get_blocked_tasks,
]

# The unified registry — every node in the Core Intelligence Layer (graph_v2) binds to
# this, so no agent path is missing calendar/module/PM capability the way the old
# query/crud/analysis agents were (they only ever saw READ_TOOLS + CRUD_TOOLS).
ALL_TOOLS = list({
    t.name: t for t in READ_TOOLS + CRUD_TOOLS + CALENDAR_TOOLS + MODULE_TOOLS + PM_TOOLS
}.values())
