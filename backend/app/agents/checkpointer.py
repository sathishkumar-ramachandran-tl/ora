"""
Durable, cross-process LangGraph checkpointer.

Replaces the in-memory `MemorySaver` (backend/app/agents/orchestrator.py), which loses
all conversation/planning state on process restart and cannot be shared across gunicorn
workers. Backed by the same Postgres database as the rest of the app.

Uses a psycopg ConnectionPool (not the short-lived `PostgresSaver.from_conn_string`
context-manager form) since this checkpointer is held for the lifetime of the process,
not a single script run.
"""
import logging

from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

logger = logging.getLogger(__name__)

_pool: ConnectionPool | None = None
_checkpointer: PostgresSaver | None = None


def get_checkpointer(database_url: str) -> PostgresSaver:
    """Return the process-wide PostgresSaver, creating (and setting up) it on first call."""
    global _pool, _checkpointer
    if _checkpointer is not None:
        return _checkpointer

    conn_string = database_url.replace('postgresql+psycopg://', 'postgresql://')
    _pool = ConnectionPool(
        conninfo=conn_string,
        min_size=1,
        max_size=10,
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    _checkpointer = PostgresSaver(_pool)
    _checkpointer.setup()  # idempotent — creates checkpoints/checkpoint_writes tables if missing
    logger.info("PostgresSaver checkpointer initialized")
    return _checkpointer
