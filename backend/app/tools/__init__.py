"""
Shared tool-implementation registry.

Plain Python functions with no LangChain/MCP-specific decoration, each returning the
canonical {"success": bool, "data": ..., "error": ...} shape. Two thin, protocol-specific
wrapper layers call into these:

  - backend/app/agents/tools.py  — LangChain @tool wrappers (in-process orchestrator)
  - backend/app/mcp_server.py    — MCP Tool wrappers (external MCP clients)

Before this package existed, those two layers each reimplemented the same business logic
independently (one talking to the DB directly, the other proxying over HTTP), and drifted —
e.g. the MCP server's update/delete task tools were stubs. Adding a new capability now means
adding one function here, not two divergent implementations.
"""
from . import task_tools

__all__ = ["task_tools"]
