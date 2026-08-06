"""
Structured logging for a professional SaaS backend.

- JSON logs in production (LOG_FORMAT=json, the default) — one line per event, machine
  parseable by CloudWatch/Datadog/etc. Falls back to a readable console formatter for
  local dev (LOG_FORMAT=console).
- Every HTTP request gets a request_id (generated, or propagated from an incoming
  X-Request-ID header) that's attached to every log line emitted during that request via
  a logging filter reading flask.g, and echoed back in the response header for tracing
  across services.
- request_id also flows into agent tool-call logging (see app/agents/llm_tracking.py)
  so a single request can be traced end-to-end: HTTP request -> LLM call -> tool call.
"""
import json
import logging
import sys
import time
import uuid

from flask import g, request, has_request_context


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(g, "request_id", None) if has_request_context() else None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Allow call sites to attach structured extras: logger.info("msg", extra={"workspace_id": "..."})
        for key, value in record.__dict__.items():
            if key in ("args", "msg", "levelname", "levelno", "pathname", "filename",
                        "module", "exc_info", "exc_text", "stack_info", "lineno",
                        "funcName", "created", "msecs", "relativeCreated", "thread",
                        "threadName", "processName", "process", "name", "request_id"):
                continue
            if key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    def __init__(self):
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )


def configure_logging(app) -> None:
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO").upper(), logging.INFO)
    fmt = app.config.get("LOG_FORMAT", "json")

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter() if fmt == "json" else ConsoleFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    app.logger.handlers = [handler]
    app.logger.setLevel(level)

    @app.before_request
    def _start_request_log():
        g.request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        g.request_start = time.monotonic()

    @app.after_request
    def _log_request(response):
        duration_ms = round((time.monotonic() - g.get("request_start", time.monotonic())) * 1000, 1)
        response.headers["X-Request-ID"] = g.get("request_id", "")
        app.logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
