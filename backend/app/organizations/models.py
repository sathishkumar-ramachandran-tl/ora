import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class Organization(db.Model):
    """Represents a Company or Institution — the 'Company' context in the application."""
    __tablename__ = 'organizations'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    name = db.Column(db.String, nullable=False)
    domain = db.Column(db.String, unique=True, nullable=True)  # e.g. 'mit.edu'
    owner_id = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    subscription_plan = db.Column(db.String, default='free')  # free, pro, enterprise
    settings = db.Column(JSONB, default=dict)  # white-labeling, SSO config, etc.


class CustomRole(db.Model):
    """A named, editable set of permissions scoped to one organization.
    See app/organizations/permissions.py for the grantable permission catalog.
    Owner/Admin/Member/Viewer defaults are seeded per-org (is_system=True) and can be
    edited or supplemented with fully custom roles."""
    __tablename__ = 'custom_roles'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    organization_id = db.Column(db.String, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    color = db.Column(db.String, default='indigo')
    permissions = db.Column(JSONB, default=list)  # list[str] of permission keys
    is_system = db.Column(db.Boolean, default=False)  # seeded default role vs admin/agent-created
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrganizationMember(db.Model):
    __tablename__ = 'organization_members'
    organization_id = db.Column(db.String, db.ForeignKey('organizations.id'), primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), primary_key=True)
    role = db.Column(db.String, default='member')  # owner | admin | member — coarse tier
    custom_role_id = db.Column(db.String, db.ForeignKey('custom_roles.id'), nullable=True)  # granular override
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String, default='active')  # active, invited, suspended
