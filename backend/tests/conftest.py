import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from app import create_app
from app.core.config import Config
from app.core.extensions import db as _db

# Deliberately NOT defaulting to Config's hardcoded Neon fallback — tests create/drop
# ALL tables against this URL on every single test function (see the `app` fixture
# below), so it must point at a database that holds nothing anyone cares about losing.
#
# 2026-08-05 incident: this used to default to the exact same
# postgresql://postgres:postgres@localhost:5432/ora_test that backend/.env's
# DATABASE_URL also pointed at for local dev. Running the suite against a live dev
# environment silently drop_all()'d every user/workspace/task in it — unrecoverable,
# no backup. The default now points at a distinctly-named database (ora_test_pytest)
# and, as a second, independent line of defense, the fixture below hard-fails if
# TEST_DATABASE_URL is ever set to match DATABASE_URL exactly, no matter what either
# variable is configured to.
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/ora_test_pytest",
)

_dev_database_url = os.environ.get("DATABASE_URL")
if _dev_database_url and _dev_database_url.rstrip("/") == TEST_DATABASE_URL.replace(
    "postgresql+psycopg://", "postgresql://"
).rstrip("/"):
    raise RuntimeError(
        "TEST_DATABASE_URL is the same database as DATABASE_URL. Refusing to run — "
        "this test suite calls db.drop_all() on every test, which would destroy real "
        "data. Point TEST_DATABASE_URL at a separate, disposable database."
    )


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL
    JWT_SECRET_KEY = "test-jwt-secret"
    SECRET_KEY = "test-secret"


@pytest.fixture()
def app():
    """Function-scoped Flask app with a fresh schema per test (create_all/drop_all)."""
    flask_app = create_app(config_class=TestConfig)
    with flask_app.app_context():
        _db.create_all()
        from app.billing.service import seed_plans
        seed_plans()
    yield flask_app
    with flask_app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    """Direct DB session access for tests that need to seed/inspect rows."""
    with app.app_context():
        yield _db
