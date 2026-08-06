import random
import logging
from datetime import datetime, timedelta

from flask import current_app

from ..core.extensions import db
from ..core.security import hash_password, verify_password, generate_token
from ..core.email import send_verification_email, send_password_reset_email, send_welcome_email
from .models import User, OAuthAccount, EmailVerificationToken, PasswordResetToken

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
RESET_TOKEN_TTL_MINUTES = 30


def register_user(email: str, password: str, name: str | None = None):
    """Returns (user, error). On success, error is None and a verification email has been sent."""
    if User.query.filter_by(email=email).first():
        return None, "An account with this email already exists"

    user = User(email=email, name=name, password_hash=hash_password(password), email_verified=False)
    db.session.add(user)
    db.session.commit()
    _issue_verification_code(user)

    from ..billing.service import create_trial_subscription
    try:
        create_trial_subscription(user_id=user.id)
    except Exception:
        logger.exception("Failed to create trial subscription", extra={"user_id": user.id})

    return user, None


def _issue_verification_code(user: User) -> str:
    # A fresh registration/resend invalidates any prior outstanding code.
    EmailVerificationToken.query.filter_by(user_id=user.id).delete()
    code = f"{random.randint(100000, 999999)}"
    token = EmailVerificationToken(
        user_id=user.id,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.session.add(token)
    db.session.commit()
    if not send_verification_email(user.email, code):
        logger.error("Failed to send verification email", extra={"user_id": user.id})
    return code


def resend_verification(user: User) -> None:
    _issue_verification_code(user)


def verify_email(user: User, code: str) -> bool:
    token = (
        EmailVerificationToken.query
        .filter_by(user_id=user.id, code=code)
        .order_by(EmailVerificationToken.created_at.desc())
        .first()
    )
    if not token or token.expires_at < datetime.utcnow():
        return False
    user.email_verified = True
    db.session.delete(token)
    db.session.commit()
    return True


def authenticate(email: str, password: str) -> User | None:
    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


def request_password_reset(email: str) -> None:
    user = User.query.filter_by(email=email).first()
    if not user:
        return  # don't reveal whether the email exists

    token_value = generate_token()
    reset = PasswordResetToken(
        user_id=user.id,
        token=token_value,
        expires_at=datetime.utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.session.add(reset)
    db.session.commit()

    reset_link = f"{current_app.config['FRONTEND_BASE_URL']}/reset-password?token={token_value}"
    if not send_password_reset_email(user.email, reset_link):
        logger.error("Failed to send password reset email", extra={"user_id": user.id})


def reset_password(token_value: str, new_password: str) -> bool:
    token = PasswordResetToken.query.filter_by(token=token_value, used=False).first()
    if not token or token.expires_at < datetime.utcnow():
        return False

    user = db.session.get(User, token.user_id)
    user.password_hash = hash_password(new_password)
    token.used = True
    db.session.commit()
    return True


def find_or_create_oauth_user(provider: str, provider_user_id: str, email: str, name: str | None) -> User:
    account = OAuthAccount.query.filter_by(provider=provider, provider_user_id=provider_user_id).first()
    if account:
        return db.session.get(User, account.user_id)

    # Same email, different sign-in method (e.g. an invited user claiming their account via OAuth) — link it.
    user = User.query.filter_by(email=email).first()
    is_new_user = not user
    if not user:
        user = User(email=email, name=name, email_verified=True)  # provider already verified the email
        db.session.add(user)
        db.session.flush()
    elif not user.email_verified:
        user.email_verified = True

    db.session.add(OAuthAccount(user_id=user.id, provider=provider, provider_user_id=provider_user_id, email=email))
    db.session.commit()

    if is_new_user:
        from ..billing.service import create_trial_subscription
        try:
            create_trial_subscription(user_id=user.id)
        except Exception:
            logger.exception("Failed to create trial subscription", extra={"user_id": user.id})

    return user


def complete_onboarding_if_needed(user: User) -> None:
    """Fires the welcome email exactly once, the moment a user finishes onboarding
    (not at raw registration — matches the product's actual 'welcomed' moment)."""
    if not user.is_onboarded:
        user.is_onboarded = True
        db.session.commit()
        if not send_welcome_email(user.email, user.name):
            logger.error("Failed to send welcome email", extra={"user_id": user.id})
