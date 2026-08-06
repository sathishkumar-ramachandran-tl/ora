import uuid
from datetime import datetime
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    context_id = db.Column(db.String)  # project id or generic

    owner_id = db.Column(db.String, db.ForeignKey('users.id'))
    visibility = db.Column(db.String, default='private')  # 'private' | 'public' | 'team'

    content = db.Column(db.Text)
    type = db.Column(db.String, default='general')
    color = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
