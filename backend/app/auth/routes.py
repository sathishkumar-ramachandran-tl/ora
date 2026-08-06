import logging

from flask import Blueprint, request, jsonify, redirect, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity

from ..core.extensions import db
from .models import User
from .oauth import oauth
from . import services

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)


def _user_json(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar": user.avatar,
        "phone": user.phone,
        "age": user.age,
        "location": user.location,
        "country": user.country,
        "purpose": user.purpose,
        "is_onboarded": user.is_onboarded,
        "email_verified": user.email_verified,
    }


# ---------------------------------------------------------------------------
# Registration / verification
# ---------------------------------------------------------------------------

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    name = data.get('name')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400

    user, error = services.register_user(email, password, name)
    if error:
        logger.info("registration_rejected", extra={"email": email, "reason": error})
        return jsonify({"error": error}), 409

    logger.info("user_registered", extra={"user_id": user.id, "email": email})
    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "user": _user_json(user)}), 201


@auth_bp.route('/verify-email', methods=['POST'])
@jwt_required()
def verify_email():
    user = db.session.get(User, get_jwt_identity())
    if not user:
        return jsonify({"error": "User not found"}), 404

    code = (request.json or {}).get('code', '').strip()
    if not services.verify_email(user, code):
        return jsonify({"error": "Invalid or expired verification code"}), 400

    return jsonify({"status": "verified", "user": _user_json(user)})


@auth_bp.route('/resend-verification', methods=['POST'])
@jwt_required()
def resend_verification():
    user = db.session.get(User, get_jwt_identity())
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.email_verified:
        return jsonify({"status": "already_verified"})

    services.resend_verification(user)
    return jsonify({"status": "sent"})


# ---------------------------------------------------------------------------
# Login / password
# ---------------------------------------------------------------------------

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    user = services.authenticate(email, password)
    if not user:
        logger.warning("login_failed", extra={"email": email})
        return jsonify({"error": "Invalid email or password"}), 401

    logger.info("login_succeeded", extra={"user_id": user.id})
    token = create_access_token(identity=user.id)
    return jsonify({"token": token, "user": _user_json(user)})


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = (request.json or {}).get('email', '').strip().lower()
    if not email:
        return jsonify({"error": "Email required"}), 400

    services.request_password_reset(email)
    # Always return success — don't leak whether the email exists.
    return jsonify({"status": "sent"})


@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json or {}
    token = data.get('token')
    new_password = data.get('password') or ''

    if not token or len(new_password) < 8:
        return jsonify({"error": "token and a password of at least 8 characters are required"}), 400

    if not services.reset_password(token, new_password):
        return jsonify({"error": "Invalid or expired reset link"}), 400

    return jsonify({"status": "reset"})


# ---------------------------------------------------------------------------
# OAuth (Google, Microsoft)
# ---------------------------------------------------------------------------

@auth_bp.route('/oauth/<provider>/login', methods=['GET'])
def oauth_login(provider):
    client = oauth.create_client(provider)
    if not client:
        return jsonify({"error": f"OAuth provider '{provider}' is not configured"}), 404

    redirect_uri = f"{current_app.config['OAUTH_REDIRECT_BASE_URL']}/api/v1/auth/oauth/{provider}/callback"
    return client.authorize_redirect(redirect_uri)


@auth_bp.route('/oauth/<provider>/callback', methods=['GET'])
def oauth_callback(provider):
    client = oauth.create_client(provider)
    if not client:
        return jsonify({"error": f"OAuth provider '{provider}' is not configured"}), 404

    frontend_url = current_app.config['FRONTEND_BASE_URL']
    try:
        token = client.authorize_access_token()
        userinfo = token.get('userinfo') or client.userinfo()
    except Exception as e:
        logger.error("OAuth callback failed", extra={"provider": provider, "error": str(e)})
        return redirect(f"{frontend_url}/login?error=oauth_failed")

    provider_user_id = userinfo.get('sub') or userinfo.get('id')
    email = userinfo.get('email')
    name = userinfo.get('name')

    if not provider_user_id or not email:
        return redirect(f"{frontend_url}/login?error=oauth_missing_profile")

    user = services.find_or_create_oauth_user(provider, provider_user_id, email, name)
    jwt = create_access_token(identity=user.id)
    return redirect(f"{frontend_url}/oauth/callback?token={jwt}")


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user = db.session.get(User, get_jwt_identity())
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_user_json(user))


@auth_bp.route('/update-profile', methods=['POST'])
@jwt_required()
def update_profile():
    user = db.session.get(User, get_jwt_identity())
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json or {}
    if not data.get('name') and not user.name:
        return jsonify({"error": "Name is required"}), 400

    if data.get('name'): user.name = data['name']
    if data.get('gender') is not None: user.gender = data['gender']
    if data.get('phone') is not None: user.phone = data['phone']
    if data.get('age') is not None: user.age = data['age']
    if data.get('location') is not None: user.location = data['location']
    if data.get('country') is not None: user.country = data['country']
    if data.get('purpose') is not None: user.purpose = data['purpose']
    db.session.commit()

    if data.get('is_onboarded'):
        services.complete_onboarding_if_needed(user)

    return jsonify({"message": "Profile updated successfully", "user": _user_json(user)})
