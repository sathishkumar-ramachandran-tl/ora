import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    name = db.Column(db.String)
    size = db.Column(db.Integer)
    type = db.Column(db.String)  # mimetype
    bucket_path = db.Column(db.String)
    tags = db.Column(JSONB, default=list)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
