"""Generic security primitives shared across domains (password hashing, opaque tokens).

RBAC/permission enforcement lives in app/organizations/permissions.py — that's a
domain-specific concern (what a permission *means*), this module is domain-agnostic
(how a password or token is generated/verified).
"""
import secrets
from werkzeug.security import generate_password_hash, check_password_hash

__all__ = ["hash_password", "verify_password", "generate_token"]


def hash_password(plain_password: str) -> str:
    return generate_password_hash(plain_password, method="pbkdf2:sha256")


def verify_password(password_hash: str, plain_password: str) -> bool:
    if not password_hash:
        return False
    return check_password_hash(password_hash, plain_password)


def generate_token(num_bytes: int = 32) -> str:
    """URL-safe random token for email verification / password reset links."""
    return secrets.token_urlsafe(num_bytes)
