import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Company(db.Model):
    """An 'Initiative' in product language — top-level grouping for projects."""
    __tablename__ = 'companies'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    name = db.Column(db.String)
    mission = db.Column(db.Text)
    color = db.Column(db.String)
    whiteboard = db.Column(JSONB, default=list)


class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    company_id = db.Column(db.String, db.ForeignKey('companies.id'))
    name = db.Column(db.String)
    type = db.Column(db.String)
    mission = db.Column(db.Text)
    progress = db.Column(db.Integer, default=0)
    whiteboard = db.Column(JSONB, default=list)


class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    project_id = db.Column(db.String, db.ForeignKey('projects.id'))
    user_id = db.Column(db.String, db.ForeignKey('users.id'))
    role = db.Column(db.String, default='contributor')  # owner, contributor, viewer
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)


class Milestone(db.Model):
    __tablename__ = 'milestones'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    project_id = db.Column(db.String, db.ForeignKey('projects.id'))
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String, default='pending')  # pending|in_progress|done
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Sprint(db.Model):
    __tablename__ = 'sprints'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    project_id = db.Column(db.String, db.ForeignKey('projects.id'))
    name = db.Column(db.String, nullable=False)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String, default='planned')  # planned|active|completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TaskDependency(db.Model):
    __tablename__ = 'task_dependencies'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=False)
    depends_on_task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=False)
    type = db.Column(db.String, default='blocks')  # blocks|blocked_by|relates_to
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('task_id', 'depends_on_task_id', 'type', name='uq_task_dependency'),
    )
