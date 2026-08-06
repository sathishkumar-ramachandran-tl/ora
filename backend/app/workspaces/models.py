import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Workspace(db.Model):
    __tablename__ = 'workspaces'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    name = db.Column(db.String)

    # Core separation: Personal vs Company
    context = db.Column(db.String, nullable=False, default='personal')  # 'personal' | 'company'
    # Core function: Study vs Project
    type = db.Column(db.String, nullable=False, default='project')  # 'study' | 'project'

    owner_id = db.Column(db.String, db.ForeignKey('users.id'))  # if personal
    organization_id = db.Column(db.String, db.ForeignKey('organizations.id'), nullable=True)  # if company

    description = db.Column(db.String)
    persona = db.Column(db.String)  # AI context

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settings = db.Column(JSONB, default=dict)

    # Enterprise fields (legacy support, prefer moving to JSONB or Organization)
    company_website = db.Column(db.String)
    location = db.Column(db.String)
    employee_count = db.Column(db.String)
    category = db.Column(db.String)
    ai_context_description = db.Column(db.String)


class WorkspaceMember(db.Model):
    __tablename__ = 'workspace_members'
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.String)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
