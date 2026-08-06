import uuid
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    project_id = db.Column(db.String, db.ForeignKey('projects.id'))
    title = db.Column(db.String)
    description = db.Column(db.Text)
    status = db.Column(db.String)
    priority = db.Column(db.String)
    estimated_hours = db.Column(db.Float)
    is_daily_focus = db.Column(db.Boolean, default=False)
    resources = db.Column(JSONB, default=list)
    # Jira-style fields
    due_date = db.Column(db.DateTime, nullable=True)
    labels = db.Column(JSONB, default=list)  # ['bug', 'frontend', ...]
    assignee_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    issue_type = db.Column(db.String, default='task')  # task|bug|feature|story
    # PM structure
    milestone_id = db.Column(db.String, db.ForeignKey('milestones.id'), nullable=True)
    sprint_id = db.Column(db.String, db.ForeignKey('sprints.id'), nullable=True)
    parent_task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=True)
    # Provenance for tasks fanned out from an installed module (Phase 1: Module Generation).
    module_instance_id = db.Column(db.String, db.ForeignKey('module_instances.id'), nullable=True)
