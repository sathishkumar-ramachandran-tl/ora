import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class ChatSession(db.Model):
    __tablename__ = 'chat_sessions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id', ondelete='CASCADE'))
    user_id = db.Column(db.String, db.ForeignKey('users.id'))
    title = db.Column(db.String, default='New Conversation')
    context = db.Column(JSONB, default=dict)
    scope_level = db.Column(db.String, default='workspace')
    scope_project_id = db.Column(db.String, db.ForeignKey('projects.id'), nullable=True)
    scope_task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    session_id = db.Column(db.String, db.ForeignKey('chat_sessions.id', ondelete='CASCADE'))
    role = db.Column(db.String, nullable=False)
    content = db.Column(db.Text)
    metadata_ = db.Column('metadata', JSONB, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
