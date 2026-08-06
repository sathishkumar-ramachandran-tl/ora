"""Shared workspace-membership check — the baseline authorization gate for every
resource that hangs off a workspace_id (tasks, projects, notes, documents, calendar
events). A user may act on a workspace if they're a WorkspaceMember of it, or the
personal owner, or (for company workspaces) a member of the owning Organization.
"""
from ..core.extensions import db


def user_can_access_workspace(user_id: str, workspace_id: str) -> bool:
    if not user_id or not workspace_id:
        return False

    from ..workspaces.models import Workspace, WorkspaceMember

    workspace = db.session.get(Workspace, workspace_id)
    if not workspace:
        return False
    if workspace.owner_id == user_id:
        return True
    if WorkspaceMember.query.filter_by(workspace_id=workspace_id, user_id=user_id).first():
        return True
    if workspace.organization_id:
        from ..organizations.models import OrganizationMember
        member = OrganizationMember.query.filter_by(
            organization_id=workspace.organization_id, user_id=user_id, status='active'
        ).first()
        if member:
            return True
    return False


def user_can_access_task(user_id: str, task) -> bool:
    return bool(task) and user_can_access_workspace(user_id, task.workspace_id)


def user_can_access_project(user_id: str, project) -> bool:
    return bool(project) and user_can_access_workspace(user_id, project.workspace_id)
