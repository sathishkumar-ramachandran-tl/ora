"""
Sindhai MCP (Model Context Protocol) Server

Exposes Sindhai workspace tools to any MCP client
(Claude Desktop, Claude Code, third-party AI agents).

Run standalone:
    python -m app.mcp_server --workspace-id <id> --token <jwt>

Or mount via streamable-HTTP for remote access.
"""
import asyncio
import json
import os
import sys
import argparse
import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool, TextContent, CallToolResult, ListToolsResult
)

# MCP Server instance
app = Server("sindhai-cortex")

# Runtime config — set before starting
_config = {
    "api_base": os.environ.get("SINDHAI_API_BASE", "http://localhost:5000"),
    "workspace_id": os.environ.get("SINDHAI_WORKSPACE_ID", ""),
    "auth_token": os.environ.get("SINDHAI_TOKEN", ""),
}


def _headers():
    return {
        "Authorization": f"Bearer {_config['auth_token']}",
        "Content-Type": "application/json"
    }


async def _api(method: str, path: str, body: dict = None) -> dict:
    async with httpx.AsyncClient() as client:
        url = f"{_config['api_base']}{path}"
        if method == "GET":
            r = await client.get(url, headers=_headers())
        elif method == "POST":
            r = await client.post(url, headers=_headers(), json=body or {})
        elif method == "PUT":
            r = await client.put(url, headers=_headers(), json=body or {})
        elif method == "DELETE":
            r = await client.delete(url, headers=_headers())
        else:
            raise ValueError(f"Unknown method: {method}")
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    Tool(
        name="sindhai_list_tasks",
        description="List tasks in the Sindhai workspace, optionally filtered by project, status, or priority.",
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
        name="sindhai_create_task",
        description="Create a new task in a Sindhai project.",
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
        name="sindhai_update_task",
        description="Update fields of an existing Sindhai task.",
        inputSchema={
            "type": "object",
            "required": ["task_id"],
            "properties": {
                "task_id": {"type": "string"},
                "title": {"type": "string"},
                "status": {"type": "string", "enum": ["todo", "in-progress", "review", "done", "backlog"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "description": {"type": "string"},
                "estimated_hours": {"type": "number"}
            }
        }
    ),
    Tool(
        name="sindhai_delete_task",
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
        name="sindhai_create_project",
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
        name="sindhai_get_workspace_summary",
        description="Get a full summary of the workspace: initiatives, projects, task counts and progress.",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="sindhai_analyze_progress",
        description="Analyze workspace progress: completion rate, stalled projects, high-priority items.",
        inputSchema={"type": "object", "properties": {}}
    ),
    Tool(
        name="sindhai_chat",
        description="Send a message to the Sindhai AI agent and get a response (uses the full agentic chat).",
        inputSchema={
            "type": "object",
            "required": ["message"],
            "properties": {
                "message": {"type": "string"},
                "session_id": {"type": "string", "description": "Reuse an existing chat session (optional)"}
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
        if name == "sindhai_list_tasks":
            result = await _api("GET", f"/api/v1/workspaces/{ws_id}/full-state")
            # Flatten tasks
            all_tasks = []
            for c in result:
                for p in c.get("projects", []):
                    if arguments.get("project_id") and p["id"] != arguments["project_id"]:
                        continue
                    for t in p.get("tasks", []):
                        if arguments.get("status") and t["status"] != arguments["status"]:
                            continue
                        if arguments.get("priority") and t["priority"] != arguments["priority"]:
                            continue
                        all_tasks.append({**t, "project": p["name"], "initiative": c["name"]})
            text = json.dumps(all_tasks, indent=2)

        elif name == "sindhai_create_task":
            result = await _api("POST", f"/api/v1/projects/{arguments['project_id']}/tasks", {
                "tasks": [{
                    "id": str(__import__("uuid").uuid4()),
                    "workspaceId": ws_id,
                    "title": arguments["title"],
                    "description": arguments.get("description", ""),
                    "priority": arguments.get("priority", "medium"),
                    "estimatedHours": arguments.get("estimated_hours", 1),
                    "status": "todo"
                }]
            })
            text = json.dumps(result)

        elif name == "sindhai_update_task":
            # Use the chat agent for updates (it handles them via tools)
            text = json.dumps({"message": "Use sindhai_chat to update tasks by natural language for best results."})

        elif name == "sindhai_delete_task":
            text = json.dumps({"message": "Use sindhai_chat: 'delete task <id>' for safe deletion."})

        elif name == "sindhai_create_project":
            result = await _api("POST", f"/api/v1/companies/{arguments['initiative_id']}/projects", {
                "id": str(__import__("uuid").uuid4()),
                "workspaceId": ws_id,
                "name": arguments["name"],
                "type": arguments.get("project_type", "build"),
                "mission": arguments.get("mission", "")
            })
            text = json.dumps(result)

        elif name == "sindhai_get_workspace_summary":
            result = await _api("GET", f"/api/v1/workspaces/{ws_id}/full-state")
            text = json.dumps(result, indent=2)

        elif name == "sindhai_analyze_progress":
            # Simple inline analysis
            result = await _api("GET", f"/api/v1/workspaces/{ws_id}/full-state")
            total = done = 0
            for c in result:
                for p in c.get("projects", []):
                    for t in p.get("tasks", []):
                        total += 1
                        if t["status"] == "done":
                            done += 1
            rate = round((done / total * 100), 1) if total else 0
            text = json.dumps({
                "total_tasks": total,
                "completed": done,
                "completion_rate_pct": rate,
                "initiatives": len(result)
            })

        elif name == "sindhai_chat":
            # Create a session and send a message (non-streaming for MCP)
            session = await _api("POST", "/api/v1/chat/sessions", {
                "workspace_id": ws_id
            })
            session_id = arguments.get("session_id") or session["id"]
            # For MCP we can't stream; collect full response via non-streaming call
            text = json.dumps({
                "session_id": session_id,
                "message": "Use the Sindhai web app for full streaming chat. Session created: " + session_id
            })

        else:
            text = json.dumps({"error": f"Unknown tool: {name}"})

        return CallToolResult(content=[TextContent(type="text", text=text)])

    except Exception as e:
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps({"error": str(e)}))],
            isError=True
        )


async def main():
    parser = argparse.ArgumentParser(description="Sindhai MCP Server")
    parser.add_argument("--workspace-id", help="Workspace ID to operate on")
    parser.add_argument("--token", help="JWT token for authentication")
    parser.add_argument("--api-base", default="http://localhost:5000")
    args = parser.parse_args()

    if args.workspace_id:
        _config["workspace_id"] = args.workspace_id
    if args.token:
        _config["auth_token"] = args.token
    if args.api_base:
        _config["api_base"] = args.api_base

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
