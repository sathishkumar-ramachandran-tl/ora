"""
Agentic Module Generation (Phase 1) — data model.

A ModuleTemplate is a marketplace listing (e.g. "UPSC Prelims in 8 months",
"GCP Data Engineering path"). Its content lives in versioned ModuleTemplateVersion
rows so an AI-generated structure can be iteratively refined without losing history;
publishing a version promotes it to the template's current listing.

A ModuleInstance is a per-workspace install of a template version: it owns one
Project (reusing the existing projects/tasks tables) plus a Milestone+Task graph
tagged via Task.module_instance_id, so AgileBoard/ScheduleView render module content
with zero special-casing.
"""
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class ModuleTemplate(db.Model):
    """A marketplace listing. `metadata` holds syllabus/prerequisite/duration content —
    JSONB rather than rigid columns because shape varies too much between e.g. an exam-prep
    module and a project-based learning path."""
    __tablename__ = 'module_templates'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    title = db.Column(db.String, nullable=False)
    slug = db.Column(db.String, unique=True, nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String, nullable=False, default='general')  # exam_prep|course|project|habit|general
    difficulty = db.Column(db.String, default='intermediate')  # beginner|intermediate|advanced
    source = db.Column(db.String, default='ai_generated')  # ai_generated|curated|community
    author_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    current_version_id = db.Column(db.String, db.ForeignKey(
        'module_template_versions.id', use_alter=True, name='fk_module_templates_current_version_id',
    ), nullable=True)
    module_metadata = db.Column('metadata', JSONB, default=dict)  # syllabus, prerequisites, estimated_duration_weeks...
    install_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModuleTemplateVersion(db.Model):
    """One generation attempt's output. `structure_json` is the phase→milestone→task
    skeleton produced by the generation graph, validated against a schema before save."""
    __tablename__ = 'module_template_versions'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    module_template_id = db.Column(db.String, db.ForeignKey('module_templates.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    structure_json = db.Column(JSONB, default=dict)
    generated_by = db.Column(db.String, default='gemini')  # gemini|human
    generation_status = db.Column(db.String, default='pending')  # pending|generating|ready|failed
    generation_error = db.Column(db.Text, nullable=True)
    critique_notes = db.Column(JSONB, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (
        db.UniqueConstraint('module_template_id', 'version', name='uq_module_template_version'),
    )


class ModuleInstance(db.Model):
    """A per-workspace install of a module template version."""
    __tablename__ = 'module_instances'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    module_template_id = db.Column(db.String, db.ForeignKey('module_templates.id'), nullable=False)
    module_template_version_id = db.Column(db.String, db.ForeignKey('module_template_versions.id'), nullable=False)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=False)
    project_id = db.Column(db.String, db.ForeignKey('projects.id'), nullable=True)
    owner_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String, default='installing')  # installing|active|completed|archived|failed
    progress_pct = db.Column(db.Integer, default=0)
    installed_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
