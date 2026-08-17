"""
Granular permission catalog for the Company/Org (RBAC) context.

Every grantable capability in the app is one string in PERMISSIONS. CustomRole.permissions
is a JSONB list of these strings. An OrganizationMember either carries a custom_role_id
(granular) or falls back to a default set derived from its coarse `role` tier.

The Owner tier is intentionally NOT permission-limited — every real SaaS RBAC system
keeps at least one unrestricted account per tenant so the org can't be locked out of its
own data by a role-editing mistake (including one the AI makes — see rbac_tools.py).
"""
from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from ..core.extensions import db
from .models import OrganizationMember, CustomRole

# --- Permission catalog ---
PERMISSIONS = {
    "org.manage_settings": "Edit organization name, domain, and settings",
    "org.manage_billing": "View and change the organization's subscription/billing",
    "org.manage_roles": "Create, edit, delete custom roles and assign them to members",
    "org.manage_members": "Invite and remove organization members",
    "org.view_members": "View the organization's member list",
    "workspace.create": "Create new workspaces under this organization",
    "workspace.manage_settings": "Edit workspace settings",
    "workspace.delete": "Delete a workspace",
    "project.create": "Create new projects",
    "project.manage": "Edit project details, manage project members",
    "project.delete": "Delete a project",
    "project.view_financials": "View project budget/financial data",
    "task.create": "Create tasks",
    "task.manage": "Edit and move tasks",
    "task.delete": "Delete tasks",
    "task.approve": "Approve tasks marked for review",
    "document.manage": "Upload and delete documents in the vault",
    "calendar.manage_org": "Create/edit organization- and team-scope calendar events",
    "payments.manage": "Manage the workspace's Circle agent wallet and spending policy",
    "payments.approve": "Approve or reject autonomous purchases pending manual review",
}

# Default permission sets for the coarse `role` tiers, used when a member has no
# custom_role_id assigned (e.g. immediately after being invited).
_DEFAULT_ADMIN_PERMISSIONS = [
    "org.manage_settings", "org.manage_roles", "org.manage_members", "org.view_members",
    "workspace.create", "workspace.manage_settings", "workspace.delete",
    "project.create", "project.manage", "project.delete", "project.view_financials",
    "task.create", "task.manage", "task.delete", "task.approve",
    "document.manage", "calendar.manage_org",
    "payments.manage", "payments.approve",
]
_DEFAULT_MEMBER_PERMISSIONS = [
    "org.view_members",
    "project.create", "project.manage",
    "task.create", "task.manage", "task.approve",
    "document.manage",
]
_DEFAULT_VIEWER_PERMISSIONS = ["org.view_members"]

SYSTEM_ROLE_TEMPLATES = {
    "Admin": _DEFAULT_ADMIN_PERMISSIONS,
    "Member": _DEFAULT_MEMBER_PERMISSIONS,
    "Viewer": _DEFAULT_VIEWER_PERMISSIONS,
}


def get_member_permissions(member: OrganizationMember) -> list[str]:
    if member.role == "owner":
        return list(PERMISSIONS.keys())
    if member.custom_role_id:
        role = db.session.get(CustomRole, member.custom_role_id)
        if role:
            return role.permissions or []
    if member.role == "admin":
        return _DEFAULT_ADMIN_PERMISSIONS
    return _DEFAULT_MEMBER_PERMISSIONS


def check_permission(user_id: str, organization_id: str, permission: str) -> bool:
    member = OrganizationMember.query.filter_by(
        organization_id=organization_id, user_id=user_id
    ).first()
    if not member or member.status != "active":
        return False
    return permission in get_member_permissions(member)


def require_permission(permission: str, org_id_arg: str = "org_id"):
    """Flask route decorator — aborts 403 unless the caller holds `permission` in the
    organization identified by the `org_id_arg` URL parameter."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            org_id = kwargs.get(org_id_arg)
            user_id = get_jwt_identity()
            if not org_id or not check_permission(user_id, org_id, permission):
                return jsonify({"error": "Forbidden", "missing_permission": permission}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
