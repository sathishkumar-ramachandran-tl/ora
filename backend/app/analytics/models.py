import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    event_name = db.Column(db.String)
    properties = db.Column(JSONB)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=True)
    session_id = db.Column(db.String, nullable=True)  # browser session
    platform = db.Column(db.String, nullable=True)  # web|mobile|api
