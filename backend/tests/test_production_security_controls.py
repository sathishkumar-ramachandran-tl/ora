from io import BytesIO

from flask_jwt_extended import create_access_token

from app.auth.models import User
from app.core.extensions import db
from app.core.security import hash_password
from app.workspaces.models import Workspace, WorkspaceMember


def _user(email="user@example.com"):
    user = User(email=email, name=email, password_hash=hash_password("password123"), email_verified=True)
    db.session.add(user)
    db.session.commit()
    return user


def _token(user):
    return create_access_token(identity=user.id)


def test_health_response_has_security_headers(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


def test_auth_rate_limit_returns_429_with_retry_after(app, client):
    app.config["RATE_LIMIT_AUTH_PER_MINUTE"] = 1

    first = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})
    second = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert int(second.headers["Retry-After"]) > 0


def test_a2a_rejects_workspace_the_user_cannot_access(app, client):
    with app.app_context():
        owner = _user("owner-a2a@example.com")
        outsider = _user("outsider-a2a@example.com")
        workspace = Workspace(id="a2a-private", name="Private", context="personal", owner_id=owner.id)
        db.session.add(workspace)
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role_id="owner"))
        db.session.commit()
        outsider_token = _token(outsider)

    resp = client.post(
        "/a2a/tasks/send",
        json={
            "id": "task-1",
            "message": {"parts": [{"text": "Summarize this workspace"}]},
            "metadata": {"workspace_id": "a2a-private"},
        },
        headers={"Authorization": f"Bearer {outsider_token}"},
    )

    assert resp.status_code == 403


def test_document_upload_rejects_disallowed_extension_before_storage(app, client):
    app.config["DOCUMENT_ALLOWED_EXTENSIONS"] = {"pdf"}
    with app.app_context():
        owner = _user("doc-owner@example.com")
        workspace = Workspace(id="doc-sec", name="Docs", context="personal", owner_id=owner.id)
        db.session.add(workspace)
        db.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=owner.id, role_id="owner"))
        db.session.commit()
        token = _token(owner)

    resp = client.post(
        "/api/v1/documents",
        data={"workspaceId": "doc-sec", "file": (BytesIO(b"hello"), "../unsafe.exe")},
        content_type="multipart/form-data",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 400
    assert resp.json["error"] == "File type is not allowed"
