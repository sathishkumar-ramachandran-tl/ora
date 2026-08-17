import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _require(name: str, hint: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. {hint}")
    return value


def _csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class Config:
    ENVIRONMENT = os.environ.get('ORA_ENV') or os.environ.get('FLASK_ENV') or 'development'
    IS_PRODUCTION = ENVIRONMENT.lower() in {'production', 'prod'}

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
    CORS_ALLOWED_ORIGINS = _csv(
        'CORS_ALLOWED_ORIGINS',
        'https://ora.teams-lab.com,https://ora-teamslab.web.app,https://ora-teamslab.firebaseapp.com,http://localhost:5173,http://localhost:3000',
    )
    if IS_PRODUCTION and not CORS_ALLOWED_ORIGINS:
        raise RuntimeError("CORS_ALLOWED_ORIGINS must be explicitly set in production.")

    AUTO_CREATE_TABLES = _bool('AUTO_CREATE_TABLES', False)
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', str(10 * 1024 * 1024)))
    DOCUMENT_MAX_UPLOAD_BYTES = int(os.environ.get('DOCUMENT_MAX_UPLOAD_BYTES', str(10 * 1024 * 1024)))
    DOCUMENT_ALLOWED_EXTENSIONS = set(_csv('DOCUMENT_ALLOWED_EXTENSIONS', 'pdf,txt,md,doc,docx,png,jpg,jpeg,csv,xlsx'))

    RATE_LIMIT_ENABLED = _bool('RATE_LIMIT_ENABLED', True)
    RATE_LIMIT_AUTH_PER_MINUTE = int(os.environ.get('RATE_LIMIT_AUTH_PER_MINUTE', '10'))
    RATE_LIMIT_AI_PER_MINUTE = int(os.environ.get('RATE_LIMIT_AI_PER_MINUTE', '20'))
    RATE_LIMIT_SEARCH_PER_MINUTE = int(os.environ.get('RATE_LIMIT_SEARCH_PER_MINUTE', '60'))
    RATE_LIMIT_MUTATION_PER_MINUTE = int(os.environ.get('RATE_LIMIT_MUTATION_PER_MINUTE', '120'))
    RATE_LIMIT_READ_PER_MINUTE = int(os.environ.get('RATE_LIMIT_READ_PER_MINUTE', '300'))

    # --- Circle Agent Wallet (Agentic Economy / USDC payments) ---
    # Without CIRCLE_API_KEY set, app/payments/circle_client.py runs in simulation
    # mode: wallets/transfers are deterministic local fixtures (clearly flagged
    # is_simulated=True everywhere) so the full acquire-capability loop is exercisable
    # without live credentials. Set these to switch to Circle's real Developer-
    # Controlled Wallets API via Circle's official Python SDK.
    CIRCLE_API_KEY = os.environ.get('CIRCLE_API_KEY')
    CIRCLE_API_BASE_URL = os.environ.get('CIRCLE_API_BASE_URL', 'https://api-sandbox.circle.com')
    # The RAW 32-byte entity secret as a 64-char hex string — generate it yourself
    # (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`) and REGISTER it
    # with Circle once (see backend/register_entity_secret.py) before first use. The
    # Circle Python SDK re-encrypts this into a fresh, single-use ciphertext on every
    # call automatically — circle_client.py never handles that encryption itself.
    CIRCLE_ENTITY_SECRET = os.environ.get('CIRCLE_ENTITY_SECRET')
    CIRCLE_WALLET_SET_ID = os.environ.get('CIRCLE_WALLET_SET_ID')
    CIRCLE_BLOCKCHAIN = os.environ.get('CIRCLE_BLOCKCHAIN', 'MATIC-AMOY')  # sandbox default
    # The USDC ERC-20/token contract address on CIRCLE_BLOCKCHAIN (not a Circle "token
    # ID" — Circle's real transfer API takes tokenAddress, confirmed against their
    # "Send tokens across wallets" guide).
    CIRCLE_USDC_TOKEN_ADDRESS = os.environ.get('CIRCLE_USDC_TOKEN_ADDRESS')
    CIRCLE_WEBHOOK_SECRET = os.environ.get('CIRCLE_WEBHOOK_SECRET')

    # --- Google Cloud Storage (Document Vault) ---
    GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')
    # GOOGLE_APPLICATION_CREDENTIALS (path to a service-account JSON key) is read directly
    # by the google-cloud-storage client via its standard credential chain — not stored here.
    # Without GCS_BUCKET_NAME set, document upload/download routes fail cleanly with a
    # clear error rather than silently no-op'ing.

    # --- Logging ---
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = os.environ.get('LOG_FORMAT', 'json')  # json | console
