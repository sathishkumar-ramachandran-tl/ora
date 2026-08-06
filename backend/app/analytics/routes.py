import logging
from datetime import datetime
from flask import Blueprint, request, jsonify

from ..core.extensions import db
from .models import ActivityLog

logger = logging.getLogger(__name__)
analytics_bp = Blueprint('analytics', __name__)


@analytics_bp.route('/analytics/event', methods=['POST'])
def log_event():
    """Fire-and-forget analytics event logging (no auth required)."""
    try:
        data = request.json or {}
        log = ActivityLog(
            id=data.get('id'),
            event_name=data.get('eventName'),
            properties=data.get('properties', {}),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat())),
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({"status": "logged"}), 200
    except Exception as e:
        logger.warning("Analytics logging failed", extra={"error": str(e)})
        return jsonify({"status": "failed"}), 500
