import uuid
from datetime import datetime
from ..core.extensions import db


def generate_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    email = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String)
    avatar = db.Column(db.String)

    # Auth
    password_hash = db.Column(db.String, nullable=True)  # null for OAuth-only accounts
    email_verified = db.Column(db.Boolean, default=False)

    # Profile Fields
    gender = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String, nullable=True)
    country = db.Column(db.String, nullable=True)
    purpose = db.Column(db.String, nullable=True)  # learning|freelancing|personal|startup|enterprise
    is_onboarded = db.Column(db.Boolean, default=False)

    # Platform-level admin (Ora staff) — distinct from org-scoped RBAC in
    # app/organizations/permissions.py, which only governs a user's own organization.
    is_platform_admin = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class OAuthAccount(db.Model):
    """Links a User to an external identity provider (Google, Microsoft)."""
    __tablename__ = 'oauth_accounts'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    provider = db.Column(db.String, nullable=False)  # 'google' | 'microsoft'
    provider_user_id = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('provider', 'provider_user_id', name='uq_oauth_provider_account'),
    )


class EmailVerificationToken(db.Model):
    """Short-lived OTP for new-user email verification only (not used for login)."""
    __tablename__ = 'email_verification_tokens'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    code = db.Column(db.String, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class PasswordResetToken(db.Model):
    """Opaque URL token (not a 6-digit OTP) emailed as a reset link."""
    __tablename__ = 'password_reset_tokens'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String, unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
