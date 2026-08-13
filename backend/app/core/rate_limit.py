import hashlib
from datetime import UTC, datetime, timedelta

from flask import current_app, g, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy.exc import SQLAlchemyError

from .extensions import db
from .models import RateLimitCounter


def _policy_for_request() -> tuple[str, int]:
    path = request.path
    method = request.method
    config = current_app.config

    if method == "OPTIONS" or path == "/health":
        return "skip", 0
    if path.startswith("/api/v1/auth/") or path.startswith("/api/v1/auth"):
        return "auth", config["RATE_LIMIT_AUTH_PER_MINUTE"]
    if path.startswith("/api/v1/chat") or "/plans" in path or "schedule-proposals" in path or "auto-schedule" in path:
        return "ai", config["RATE_LIMIT_AI_PER_MINUTE"]
    if path.endswith("/search") or "/search" in path:
        return "search", config["RATE_LIMIT_SEARCH_PER_MINUTE"]
    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "mutation", config["RATE_LIMIT_MUTATION_PER_MINUTE"]
    return "read", config["RATE_LIMIT_READ_PER_MINUTE"]


def _identity_key(policy: str) -> str:
    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
    except Exception:
        user_id = None

    if user_id:
        workspace_id = (
            (request.view_args or {}).get("ws_id")
            or (request.view_args or {}).get("workspace_id")
            or (request.get_json(silent=True) or {}).get("workspace_id")
            or (request.get_json(silent=True) or {}).get("workspaceId")
            or "-"
        )
        return f"user:{user_id}:workspace:{workspace_id}:policy:{policy}"
    return f"ip:{request.remote_addr or 'unknown'}:policy:{policy}"


def check_rate_limit():
    if not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return None

    policy, limit = _policy_for_request()
    if policy == "skip" or limit <= 0:
        return None

    now = datetime.now(UTC).replace(tzinfo=None)
    window_start = now.replace(second=0, microsecond=0)
    key_hash = hashlib.sha256(_identity_key(policy).encode("utf-8")).hexdigest()

    try:
        counter = RateLimitCounter.query.filter_by(key_hash=key_hash, policy=policy).first()
        if not counter:
            counter = RateLimitCounter(key_hash=key_hash, policy=policy, window_start=window_start, count=1)
            db.session.add(counter)
        elif counter.window_start < window_start:
            counter.window_start = window_start
            counter.count = 1
        else:
            counter.count += 1

        g.rate_limit_policy = policy
        g.rate_limit_remaining = max(limit - counter.count, 0)

        if counter.count > limit:
            db.session.commit()
            retry_after = max(1, int((window_start + timedelta(minutes=1) - now).total_seconds()))
            current_app.logger.warning(
                "rate_limit_exceeded",
                extra={"policy": policy, "path": request.path, "method": request.method},
            )
            response = jsonify({"error": "Rate limit exceeded", "retryAfter": retry_after})
            response.status_code = 429
            response.headers["Retry-After"] = str(retry_after)
            return response

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception(
            "rate_limit_check_failed",
            extra={"policy": policy, "path": request.path, "method": request.method},
        )
    return None
