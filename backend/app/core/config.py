import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _require(name: str, hint: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. {hint}")
    return value


class Config:
    # No hardcoded fallback, deliberately — a guessable default signing key here means
    # anyone who's read this file (public repo) can forge valid sessions/JWTs against any
    # deployment that forgot to set the env var. Same fail-fast pattern as DATABASE_URL.
    SECRET_KEY = _require(
        'SECRET_KEY',
        "Set a random 32+ byte value, e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`."
    )

    SQLALCHEMY_DATABASE_URI = _require(
        'DATABASE_URL',
        "Copy backend/.env.example to backend/.env and point it at your own Postgres "
        "instance (no default is provided to avoid accidentally connecting to a shared database)."
    ).replace('postgresql://', 'postgresql+psycopg://')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = _require(
        'JWT_SECRET_KEY',
        "Set a random 32+ byte value, e.g. `python -c \"import secrets; print(secrets.token_hex(32))\"`."
    )
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    API_KEY = os.environ.get('API_KEY')  # Gemini API Key

    # --- Amazon SES (all transactional email: welcome, verify-email, password reset) ---
    AWS_REGION = os.environ.get('AWS_REGION', 'ap-south-1')
    SES_SENDER_EMAIL = os.environ.get('SES_SENDER_EMAIL', 'no-reply@ora.teams-lab.com')
    # AWS credentials are read from the standard boto3 chain (env vars / IAM role / ~/.aws
    # credentials) — not stored here. Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY in the
    # environment, or attach an IAM role with ses:SendEmail when deployed.

    # --- OAuth (Google + Microsoft) ---
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET')
    MICROSOFT_OAUTH_CLIENT_ID = os.environ.get('MICROSOFT_OAUTH_CLIENT_ID')
    MICROSOFT_OAUTH_CLIENT_SECRET = os.environ.get('MICROSOFT_OAUTH_CLIENT_SECRET')
    MICROSOFT_OAUTH_TENANT = os.environ.get('MICROSOFT_OAUTH_TENANT', 'common')
    OAUTH_REDIRECT_BASE_URL = os.environ.get('OAUTH_REDIRECT_BASE_URL', 'http://localhost:5000')

    # --- Stripe ---
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

    FRONTEND_BASE_URL = os.environ.get('FRONTEND_BASE_URL', 'http://localhost:3000')

    # --- Google Cloud Storage (Document Vault) ---
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
    # GOOGLE_APPLICATION_CREDENTIALS (path to a service-account JSON key) is read directly
    # by the google-cloud-storage client via its standard credential chain — not stored here.
    # Without GCS_BUCKET_NAME set, document upload/download routes fail cleanly with a
    # clear error rather than silently no-op'ing.

    # --- Logging ---
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 'json')  # json | console
