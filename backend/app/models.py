"""
Cross-domain model registry.

Model *definitions* live next to their domain's routes/services (app/auth/models.py,
app/projects/models.py, etc.) — that's the actual organizational win of the reorg.
This module re-exports all of them for the handful of genuinely cross-domain consumers
that need to touch many domains at once (the shared tool registry in app/tools/, tests,
Alembic autogenerate) so they don't need N import lines from N domain packages.

Importing every domain's models module here also guarantees they're all registered on
`db.metadata` before db.create_all()/Alembic run, regardless of which domain package
happens to be imported first elsewhere.
"""
from .auth.models import User, OAuthAccount, EmailVerificationToken, PasswordResetToken
from .organizations.models import Organization, OrganizationMember, CustomRole
from .workspaces.models import Workspace, WorkspaceMember
from .projects.models import Company, Project, ProjectMember, Milestone, Sprint, TaskDependency
from .tasks.models import Task
from .notes.models import Note
from .documents.models import Document
from .calendar.models import CalendarEvent
from .analytics.models import ActivityLog
from .chat.models import ChatSession, ChatMessage
from .agents.models import AgentToolCall, PlanningSession, LlmCall
from .billing.models import Plan, Subscription, PlanOverride, PromoCode, PromoRedemption, PlatformSetting
from .modules.models import ModuleTemplate, ModuleTemplateVersion, ModuleInstance

__all__ = [
    "User", "OAuthAccount", "EmailVerificationToken", "PasswordResetToken",
    "Organization", "OrganizationMember", "CustomRole",
    "Workspace", "WorkspaceMember",
    "Company", "Project", "ProjectMember", "Milestone", "Sprint", "TaskDependency",
    "Task",
    "Note",
    "Document",
    "CalendarEvent",
    "ActivityLog",
    "ChatSession", "ChatMessage",
    "AgentToolCall", "PlanningSession", "LlmCall",
    "ModuleTemplate", "ModuleTemplateVersion", "ModuleInstance",
]
