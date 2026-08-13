import uuid
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    organization_id = db.Column(db.String, db.ForeignKey(
        'organizations.id', name='fk_calendar_events_organization_id',
    ), nullable=True)
    owner_id = db.Column(db.String, db.ForeignKey('users.id'))  # creator/owner
    title = db.Column(db.String)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    type = db.Column(db.String)  # 'task_block', 'meeting', 'personal', 'reminder'
    scope = db.Column(db.String, default='personal')  # 'personal', 'workspace', 'company'
    task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=True)
    color = db.Column(db.String, default='blue')
    is_auto_generated = db.Column(db.Boolean, default=False)
    # IANA name (e.g. 'Asia/Kolkata') — start_time/end_time are stored naive in this zone;
    # without it a company's multi-timezone members can't be reasoned about consistently.
    timezone = db.Column(db.String, default='UTC')
    # RFC5545 RRULE text (e.g. 'FREQ=WEEKLY;BYDAY=MO,WE,FR'), null for one-off events.
    recurrence_rule = db.Column(db.String, nullable=True)
    # Set on materialized occurrences of a recurring series, pointing at the defining event.
    recurrence_parent_id = db.Column(db.String, db.ForeignKey(
        'calendar_events.id', name='fk_calendar_events_recurrence_parent_id',
    ), nullable=True)
    # user_id list — who beyond owner_id can see a scope='workspace'/'company' event.
    attendees = db.Column(JSONB, default=list)
    # Scheduling semantics for Ora's first-party calendar. A task may have many
    # task_block sessions; completing a session is distinct from completing the task.
    is_flexible = db.Column(db.Boolean, default=True)
    locked = db.Column(db.Boolean, default=False)
    session_status = db.Column(db.String, default='SCHEDULED')  # SCHEDULED|COMPLETED|MISSED|CANCELLED
    completed_at = db.Column(db.DateTime, nullable=True)
