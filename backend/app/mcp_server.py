"""
Ora MCP (Model Context Protocol) Server

Exposes Ora workspace tools to any MCP client
(Claude Desktop, Claude Code, third-party AI agents).

Run standalone:
    python -m app.mcp_server --workspace-id <id> --user-id <id>

Calls the same shared tool implementations (app/tools/task_tools.py) as the in-process
LangChain orchestrator (app/agents/tools.py) — this process holds its own Flask app
context and talks to the database directly, rather than proxying over HTTP to a running
Flask server. That's what keeps this catalog and the orchestrator's catalog from
drifting: one implementation, two thin protocol-specific wrapper layers.
"""
import asyncio
import json
import os
import argparse
from datetime import datetime
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool, TextContent, CallToolResult, ListToolsResult
)

from app import create_app
from app.core.extensions import db
from app.agents.action_executor import create_agent_run
from app.agents.control_plane import AgentRunStatus
from app.agents.execution_context import ExecutionContext, execution_context, get_execution_context
from app.tools import task_tools, module_tools, calendar_tools

# MCP Server instance
app = Server("ora-cortex")

# Runtime config — set before starting
_config = {
    "workspace_id": os.environ.get("ORA_WORKSPACE_ID", ""),
    "user_id": os.environ.get("ORA_USER_ID", ""),
}

_flask_app = None


def _result(payload: dict) -> dict:
    """Unwrap the shared {success, data, error} shape for MCP text output."""
    if payload["success"]:
        return payload["data"]
    return {"error": payload["error"]}


def _new_context(session_id: str | None = None, run_id: str | None = None) -> ExecutionContext:
    import uuid

    return ExecutionContext(
        request_id=str(uuid.uuid4()),
        user_id=_config.get("user_id", ""),
        workspace_id=_config.get("workspace_id", ""),
        session_id=session_id,
        run_id=run_id or str(uuid.uuid4()),
    )


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="ora_list_tasks",
        description="List tasks in the Ora workspace, optionally filtered by project, status, or priority.",
        inputSchema={
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Filter by project ID (optional)"},
                "status": {"type": "string", "enum": ["todo", "in-progress", "review", "done", "backlog"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]}
            }
        }
    ),
    Tool(
        name="ora_create_task",
        description="Create a new task in a Ora project.",
        inputSchema={
            "type": "object",
            "required": ["project_id", "title"],
            "properties": {
                "project_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"], "default": "medium"},
                "estimated_hours": {"type": "number", "default": 1}
            }
        }
    ),
    Tool(
        name="ora_update_task",
        description="Update fields of an existing Ora task.",
        inputSchema={
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string"},
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["todo", "in-progress", "review", "done", "backlog"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "description": {"type": "string"},
                "estimated_hours": {"type": "number"},
                "assignee_id": {"type": "string", "description": "User id to assign this task to — resolve a name via ora_list_workspace_members first"}
            }
        }
    ),
    Tool(
        name="ora_delete_task",
        description="Permanently delete a task from the workspace.",
        inputSchema={
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string"}
            }
        }
    ),
    Tool(
        name="ora_create_project",
        description="Create a new project under an initiative in the workspace.",
        inputSchema={
            "type": "object",
            "required": ["initiative_id", "name"],
            "properties": {
                "initiative_id": {"type": "string"},
                "name": {"type": "string"},
                "project_type": {"type": "string", "enum": ["build", "learning", "research", "client", "campaign"]},
                "mission": {"type": "string"}
            }
        }
    ),
    Tool(
        name="ora_get_workspace_summary",
        description="Get a full summary of the workspace: initiatives, projects, task counts and progress.",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="ora_analyze_progress",
        description="Analyze workspace progress: completion rate, stalled projects, high-priority items.",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="ora_list_workspace_members",
        description="List the people (id, name, email) who are members of this workspace — use to resolve a name to a user id before assigning a task.",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="ora_list_modules",
        description="Browse published modules in the Ora marketplace (e.g. exam-prep, course, or project templates), optionally filtered by category.",
        inputSchema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "exam_prep|course|project|habit|general (optional)"}
            }
        }
    ),
    Tool(
        name="ora_generate_module",
        description="Generate a new module (a phase-by-phase milestone+task plan) for a goal, e.g. 'UPSC prep in 8 months'. Runs asynchronously — returns immediately with an id to poll via ora_get_module_progress.",
        inputSchema={
            "type": "object",
            "required": ["goal"],
            "properties": {
                "goal": {"type": "string"},
                "title": {"type": "string"},
                "category": {"type": "string", "enum": ["exam_prep", "course", "project", "habit", "general"], "default": "general"},
                "difficulty": {"type": "string", "enum": ["beginner", "intermediate", "advanced"], "default": "intermediate"}
            }
        }
    ),
    Tool(
        name="ora_get_module_progress",
        description="Check generation progress/status for a module template (pending|generating|ready|failed).",
        inputSchema={
            "type": "object",
            "required": ["module_template_id"],
            "properties": {"module_template_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_install_module",
        description="Install a ready module into the workspace — fans its milestone/task structure out into a real project.",
        inputSchema={
            "type": "object",
            "required": ["module_template_id"],
            "properties": {"module_template_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_list_events",
        description="List calendar events in a window, expanding recurring events into concrete occurrences. Respects personal/workspace/company visibility scoping.",
        inputSchema={
            "type": "object",
            "required": ["start", "end"],
            "properties": {
                "start": {"type": "string", "description": "ISO 8601 window start"},
                "end": {"type": "string", "description": "ISO 8601 window end"},
                "scope": {"type": "string", "enum": ["personal", "workspace", "company"], "description": "Filter to one scope (optional)"}
            }
        }
    ),
    Tool(
        name="ora_create_event",
        description="Create a calendar event, optionally recurring (RFC5545 RRULE) or scoped to workspace/company visibility.",
        inputSchema={
            "type": "object",
            "required": ["title", "start", "end"],
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 start"},
                "end": {"type": "string", "description": "ISO 8601 end"},
                "type": {"type": "string", "enum": ["task_block", "meeting", "personal", "reminder"], "default": "personal"},
                "scope": {"type": "string", "enum": ["personal", "workspace", "company"], "default": "personal"},
                "task_id": {"type": "string"},
                "color": {"type": "string", "default": "blue"},
                "timezone": {"type": "string", "default": "UTC"},
                "recurrence_rule": {"type": "string", "description": "RFC5545 RRULE text, e.g. 'FREQ=WEEKLY;BYDAY=MO,WE,FR' (optional)"},
                "attendees": {"type": "array", "items": {"type": "string"}, "description": "User IDs, beyond the owner, who can see this event (optional)"}
            }
        }
    ),
    Tool(
        name="ora_update_event",
        description="Update fields of an existing calendar event.",
        inputSchema={
            "type": "object",
            "required": ["event_id"],
            "properties": {
                "event_id": {"type": "string"},
                "title": {"type": "string"},
                "start": {"type": "string"},
                "end": {"type": "string"},
                "color": {"type": "string"},
                "scope": {"type": "string", "enum": ["personal", "workspace", "company"]}
            }
        }
    ),
    Tool(
        name="ora_delete_event",
        description="Delete a calendar event, optionally its entire recurring series.",
        inputSchema={
            "type": "object",
            "required": ["event_id"],
            "properties": {
                "event_id": {"type": "string"},
                "delete_series": {"type": "boolean", "default": False}
            }
        }
    ),
    Tool(
        name="ora_find_availability",
        description="Scan attendees' events for open slots within working hours. The scheduling intelligence tool, not just CRUD.",
        inputSchema={
            "type": "object",
            "required": ["duration_minutes", "window_start", "window_end"],
            "properties": {
                "attendee_user_ids": {"type": "array", "items": {"type": "string"}, "description": "Defaults to the current user"},
                "duration_minutes": {"type": "integer"},
                "window_start": {"type": "string"},
                "window_end": {"type": "string"},
                "day_start_hour": {"type": "integer", "default": 9},
                "day_end_hour": {"type": "integer", "default": 18}
            }
        }
    ),
    Tool(
        name="ora_auto_schedule_tasks",
        description="Auto-schedule tasks into real free calendar slots (calendar-aware — never invents a schedule). Without task_ids, schedules every open, not-yet-scheduled task in the workspace, highest priority first.",
        inputSchema={
            "type": "object",
            "properties": {
                "task_ids": {"type": "array", "items": {"type": "string"}, "description": "Specific tasks to schedule; omit to auto-select all open unscheduled tasks"},
                "day_start_hour": {"type": "integer", "default": 9},
                "day_end_hour": {"type": "integer", "default": 18},
                "weekdays_only": {"type": "boolean", "default": True},
                "target_end_date": {"type": "string", "description": "ISO date cap on how far out to look; defaults to 14 days out"},
                "block_hours": {"type": "number", "description": "Override each task's estimated_hours for the block duration"}
            }
        }
    ),
    Tool(
        name="ora_schedule_module_milestones",
        description="Read an installed module's milestones and auto-create task_block focus events for them, placed via ora_find_availability so they land in genuinely free time.",
        inputSchema={
            "type": "object",
            "required": ["module_instance_id"],
            "properties": {
                "module_instance_id": {"type": "string"},
                "block_hours": {"type": "number", "default": 2.0}
            }
        }
    ),
    Tool(
        name="ora_create_milestone",
        description="Create a milestone under a project.",
        inputSchema={
            "type": "object",
            "required": ["project_id", "title"],
            "properties": {
                "project_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "due_date": {"type": "string", "description": "ISO 8601 date/datetime (optional)"},
                "order": {"type": "integer", "default": 0}
            }
        }
    ),
    Tool(
        name="ora_list_milestones",
        description="List milestones for a project, ordered by sequence.",
        inputSchema={
            "type": "object",
            "required": ["project_id"],
            "properties": {"project_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_update_milestone",
        description="Update fields of an existing milestone.",
        inputSchema={
            "type": "object",
            "required": ["milestone_id"],
            "properties": {
                "milestone_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "due_date": {"type": "string"},
                "status": {"type": "string", "enum": ["pending", "in_progress", "done"]},
                "order": {"type": "integer"}
            }
        }
    ),
    Tool(
        name="ora_delete_milestone",
        description="Delete a milestone. Linked tasks are unlinked, not deleted.",
        inputSchema={
            "type": "object",
            "required": ["milestone_id"],
            "properties": {"milestone_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_create_sprint",
        description="Create a sprint under a project.",
        inputSchema={
            "type": "object",
            "required": ["project_id", "name"],
            "properties": {
                "project_id": {"type": "string"},
                "name": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "status": {"type": "string", "enum": ["planned", "active", "completed"], "default": "planned"}
            }
        }
    ),
    Tool(
        name="ora_list_sprints",
        description="List sprints for a project.",
        inputSchema={
            "type": "object",
            "required": ["project_id"],
            "properties": {"project_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_update_sprint",
        description="Update fields of an existing sprint.",
        inputSchema={
            "type": "object",
            "required": ["sprint_id"],
            "properties": {
                "sprint_id": {"type": "string"},
                "name": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "status": {"type": "string", "enum": ["planned", "active", "completed"]}
            }
        }
    ),
    Tool(
        name="ora_delete_sprint",
        description="Delete a sprint. Linked tasks are unlinked, not deleted.",
        inputSchema={
            "type": "object",
            "required": ["sprint_id"],
            "properties": {"sprint_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_add_dependency",
        description="Declare that a task depends on another task (blocked until it's done). Rejected if it would create a cycle.",
        inputSchema={
            "type": "object",
            "required": ["task_id", "depends_on_task_id"],
            "properties": {
                "task_id": {"type": "string"},
                "depends_on_task_id": {"type": "string"},
                "dependency_type": {"type": "string", "enum": ["blocks", "blocked_by", "relates_to"], "default": "blocks"}
            }
        }
    ),
    Tool(
        name="ora_remove_dependency",
        description="Remove a task dependency link.",
        inputSchema={
            "type": "object",
            "required": ["dependency_id"],
            "properties": {"dependency_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_get_blocked_tasks",
        description="List tasks in a project that are currently blocked by an incomplete dependency — the dependency-graph read tool for planning around blockers.",
        inputSchema={
            "type": "object",
            "required": ["project_id"],
            "properties": {"project_id": {"type": "string"}}
        }
    ),
    Tool(
        name="ora_replan_project",
        description="AI-replan an existing project: invokes the Core Intelligence Layer's planner/executor/reflect loop scoped to this project to add/update milestones, sprints, tasks, and dependencies toward a stated goal.",
        inputSchema={
            "type": "object",
            "required": ["project_id", "goal"],
            "properties": {
                "project_id": {"type": "string"},
                "goal": {"type": "string", "description": "What should change, e.g. 'add a QA milestone before launch'"}
            }
        }
    ),
    Tool(
        name="ora_chat",
        description="Send a message to the Ora AI agent and get a response (uses the full agentic multi-agent orchestrator).",
        inputSchema={
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {"type": "string"},
                "session_id": {"type": "string", "description": "Reuse an existing thread for multi-turn context (optional)"}
            }
        }
    )
]


@app.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(tools=TOOLS)


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> CallToolResult:
    ws_id = _config["workspace_id"]

    try:
        with _flask_app.app_context():
            ctx = _new_context(session_id=arguments.get("session_id") if name == "ora_chat" else None)
            create_agent_run(ctx)
            with execution_context(ctx):
                result = _dispatch_tool(name, arguments, ws_id)

        text = json.dumps(result, indent=2, default=str)
        return CallToolResult(content=[TextContent(type="text", text=text)])

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": str(e)}))],
            isError=True
        )


def _dispatch_tool(name: str, arguments: dict, ws_id: str) -> dict:
    if name == "ora_list_tasks":
        return _result(task_tools.get_tasks(
            ws_id,
            arguments.get("project_id"),
            arguments.get("status"),
            arguments.get("priority"),
        ))

    if name == "ora_create_task":
        return _result(task_tools.create_task(
            arguments["project_id"], ws_id, arguments["title"],
            arguments.get("description", ""),
            arguments.get("priority", "medium"),
            arguments.get("estimated_hours", 1.0),
        ))

    if name == "ora_update_task":
        return _result(task_tools.update_task(
            arguments["task_id"],
            title=arguments.get("title"),
            description=arguments.get("description"),
            status=arguments.get("status"),
            priority=arguments.get("priority"),
            estimated_hours=arguments.get("estimated_hours"),
            assignee_id=arguments.get("assignee_id"),
        ))

    if name == "ora_delete_task":
        return _result(task_tools.delete_task(arguments["task_id"]))

    if name == "ora_create_project":
        return _result(task_tools.create_project(
            arguments["initiative_id"], ws_id, arguments["name"],
            arguments.get("project_type", "build"),
            arguments.get("mission", ""),
        ))

    if name == "ora_get_workspace_summary":
        return _result(task_tools.get_workspace_summary(ws_id))

    if name == "ora_analyze_progress":
        return _result(task_tools.analyze_workspace_progress(ws_id))

    if name == "ora_list_workspace_members":
        return _result(task_tools.list_workspace_members(ws_id))

    if name == "ora_list_modules":
        return _result(module_tools.list_modules(category=arguments.get("category")))

    if name == "ora_generate_module":
        goal = arguments["goal"]
        draft = module_tools.create_module_draft(
            title=arguments.get("title") or goal[:80],
            description=goal,
            category=arguments.get("category", "general"),
            difficulty=arguments.get("difficulty", "intermediate"),
            author_id=_config["user_id"],
        )
        if draft["success"]:
            module_tools.start_generation(
                _flask_app,
                module_template_id=draft["data"]["moduleTemplateId"],
                module_template_version_id=draft["data"]["moduleTemplateVersionId"],
                goal=goal,
                category=arguments.get("category", "general"),
                difficulty=arguments.get("difficulty", "intermediate"),
            )
        return _result(draft)

    if name == "ora_get_module_progress":
        return _result(module_tools.get_generation_progress_by_template(arguments["module_template_id"]))

    if name == "ora_install_module":
        return _result(module_tools.install_module(arguments["module_template_id"], ws_id, _config["user_id"]))

    if name == "ora_list_events":
        return _result(calendar_tools.list_events(
            ws_id, _config["user_id"],
            datetime.fromisoformat(arguments["start"]),
            datetime.fromisoformat(arguments["end"]),
            scope=arguments.get("scope"),
        ))

    if name == "ora_create_event":
        return _result(calendar_tools.create_event(
            ws_id, _config["user_id"], arguments["title"],
            datetime.fromisoformat(arguments["start"]),
            datetime.fromisoformat(arguments["end"]),
            event_type=arguments.get("type", "personal"),
            scope=arguments.get("scope", "personal"),
            task_id=arguments.get("task_id"),
            color=arguments.get("color", "blue"),
            timezone=arguments.get("timezone", "UTC"),
            recurrence_rule=arguments.get("recurrence_rule"),
            attendees=arguments.get("attendees"),
        ))

    if name == "ora_update_event":
        return _result(calendar_tools.update_event(
            arguments["event_id"],
            title=arguments.get("title"),
            start=datetime.fromisoformat(arguments["start"]) if arguments.get("start") else None,
            end=datetime.fromisoformat(arguments["end"]) if arguments.get("end") else None,
            color=arguments.get("color"),
            scope=arguments.get("scope"),
        ))

    if name == "ora_delete_event":
        return _result(calendar_tools.delete_event(arguments["event_id"], delete_series=arguments.get("delete_series", False)))

    if name == "ora_find_availability":
        return _result(calendar_tools.find_availability(
            ws_id,
            arguments.get("attendee_user_ids") or [_config["user_id"]],
            arguments["duration_minutes"],
            datetime.fromisoformat(arguments["window_start"]),
            datetime.fromisoformat(arguments["window_end"]),
            day_start_hour=arguments.get("day_start_hour", 9),
            day_end_hour=arguments.get("day_end_hour", 18),
        ))

    if name == "ora_auto_schedule_tasks":
        return _result(calendar_tools.auto_schedule_tasks(
            ws_id, _config["user_id"],
            task_ids=arguments.get("task_ids"),
            day_start_hour=arguments.get("day_start_hour", 9),
            day_end_hour=arguments.get("day_end_hour", 18),
            weekdays_only=arguments.get("weekdays_only", True),
            window_end=arguments.get("target_end_date"),
            block_hours=arguments.get("block_hours"),
        ))

    if name == "ora_schedule_module_milestones":
        return _result(calendar_tools.schedule_module_milestones(
            arguments["module_instance_id"], ws_id, _config["user_id"],
            block_hours=arguments.get("block_hours", 2.0),
        ))

    if name == "ora_create_milestone":
        return _result(task_tools.create_milestone(
            arguments["project_id"], arguments["title"],
            arguments.get("description", ""), arguments.get("due_date"),
            arguments.get("order", 0),
        ))

    if name == "ora_list_milestones":
        return _result(task_tools.list_milestones(arguments["project_id"]))

    if name == "ora_update_milestone":
        return _result(task_tools.update_milestone(
            arguments["milestone_id"],
            title=arguments.get("title"),
            description=arguments.get("description"),
            due_date=arguments.get("due_date"),
            status=arguments.get("status"),
            order=arguments.get("order"),
        ))

    if name == "ora_delete_milestone":
        return _result(task_tools.delete_milestone(arguments["milestone_id"]))

    if name == "ora_create_sprint":
        return _result(task_tools.create_sprint(
            arguments["project_id"], arguments["name"],
            arguments.get("start_date"), arguments.get("end_date"),
            arguments.get("status", "planned"),
        ))

    if name == "ora_list_sprints":
        return _result(task_tools.list_sprints(arguments["project_id"]))

    if name == "ora_update_sprint":
        return _result(task_tools.update_sprint(
            arguments["sprint_id"],
            name=arguments.get("name"),
            start_date=arguments.get("start_date"),
            end_date=arguments.get("end_date"),
            status=arguments.get("status"),
        ))

    if name == "ora_delete_sprint":
        return _result(task_tools.delete_sprint(arguments["sprint_id"]))

    if name == "ora_add_dependency":
        return _result(task_tools.add_task_dependency(
            arguments["task_id"], arguments["depends_on_task_id"],
            arguments.get("dependency_type", "blocks"),
        ))

    if name == "ora_remove_dependency":
        return _result(task_tools.remove_task_dependency(arguments["dependency_id"]))

    if name == "ora_get_blocked_tasks":
        return _result(task_tools.get_blocked_tasks(arguments["project_id"]))

    if name == "ora_replan_project":
        return _result(task_tools.replan_project(arguments["project_id"], ws_id, _config["user_id"], arguments["goal"]))

    if name == "ora_chat":
        return _run_chat(arguments["message"], arguments.get("session_id"))

    return {"error": f"Unknown tool: {name}"}


def _run_chat(message: str, session_id: str | None) -> dict:
    """Invoke the LangGraph orchestrator synchronously (MCP's stdio transport has no
    SSE-equivalent streaming, so this blocks for the full response — same non-streaming
    trade-off as the /a2a/tasks/send endpoint)."""
    import uuid as _uuid
    from langchain_core.messages import HumanMessage
    from app.agents.models import AgentRun

    engine = os.environ.get("AGENT_ENGINE", "v2")
    if engine == "v1":
        from app.agents.orchestrator import create_orchestrator
    else:
        from app.agents.graph_v2 import create_orchestrator

    thread_id = session_id or f"mcp_{_uuid.uuid4()}"
    ctx = get_execution_context(required=False)
    local_context = None
    if ctx is None:
        local_context = _new_context(session_id=thread_id)
        create_agent_run(local_context)
        ctx_manager = execution_context(local_context)
        ctx_manager.__enter__()
        ctx = local_context
    else:
        ctx_manager = None

    orchestrator = create_orchestrator()
    base_state = {
        "messages": [HumanMessage(content=message)],
        "workspace_id": _config["workspace_id"],
        "user_id": _config["user_id"],
        "workspace_context": {},
        "planning_phase": None,
        "draft_plan": {},
        "planning_project_id": None,
    }
    if engine == "v1":
        state = {**base_state, "intent": None}
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 20}
    else:
        state = {
            **base_state,
            "complexity": None,
            "goal": None,
            "plan": [],
            "working_memory": {},
            "current_step_index": 0,
            "replan_count": 0,
            "next_action": None,
            "final_answer": None,
        }
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 50}

    try:
        result = orchestrator.invoke(state, config=config)
        last_msg = result["messages"][-1]
        response_text = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
        run = db.session.get(AgentRun, ctx.run_id) if ctx and ctx.run_id else None
        if run and run.status == AgentRunStatus.RUNNING.value:
            run.status = AgentRunStatus.COMPLETED.value
            run.completed_at = datetime.utcnow()
            db.session.commit()
        return {"session_id": thread_id, "response": response_text}
    finally:
        if ctx_manager is not None:
            ctx_manager.__exit__(None, None, None)


async def main():
    global _flask_app

    parser = argparse.ArgumentParser(description="Ora MCP Server")
    parser.add_argument("--workspace-id", help="Workspace ID to operate on")
    parser.add_argument("--user-id", help="User ID to attribute actions to (for ora_chat)")
    args = parser.parse_args()

    if args.workspace_id:
        _config["workspace_id"] = args.workspace_id
    if args.user_id:
        _config["user_id"] = args.user_id

    if not _config["workspace_id"]:
        raise SystemExit("--workspace-id (or ORA_WORKSPACE_ID) is required")

    _flask_app = create_app()

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
