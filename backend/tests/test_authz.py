"""Regression tests for the broken-access-control fixes found during the security
hardening pass: users must not be able to read/write resources in a workspace they
don't belong to just by knowing its ID."""
from flask_jwt_extended import create_access_token

from app.core.extensions import db
from app.auth.models import User
from app.workspaces.models import Workspace, WorkspaceMember
from app.tasks.models import Task
from app.core.security import hash_password


def _make_user(email):
    user = User(email=email, name=email, password_hash=hash_password("pw"), email_verified=True)
    db.session.add(user)
    db.session.commit()
    return user


def _token(user):
    return create_access_token(identity=user.id)


def test_non_member_cannot_read_workspace_members(app, client, db):
    with app.app_context():
        owner = _make_user("owner@example.com")
        outsider = _make_user("outsider@example.com")
        ws = Workspace(id="ws-authz-1", name="Private WS", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role_id="owner"))
        db.session.commit()
        outsider_token = _token(outsider)

    resp = client.get(
        "/api/v1/workspaces/ws-authz-1/members",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


def test_member_can_read_workspace_members(app, client, db):
    with app.app_context():
        owner = _make_user("owner2@example.com")
        ws = Workspace(id="ws-authz-2", name="WS 2", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role_id="owner"))
        db.session.commit()
        owner_token = _token(owner)

    resp = client.get(
        "/api/v1/workspaces/ws-authz-2/members",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert resp.status_code == 200


def test_non_member_cannot_read_or_write_another_users_task(app, client, db):
    with app.app_context():
        owner = _make_user("taskowner@example.com")
        outsider = _make_user("taskoutsider@example.com")
        ws = Workspace(id="ws-authz-3", name="Task WS", context="personal", owner_id=owner.id)
        db.session.add(ws)
        db.session.flush()
        db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=owner.id, role_id="owner"))
        task = Task(id="task-authz-1", workspace_id=ws.id, title="Secret task", status="todo", priority="medium")
        db.session.add(task)
        db.session.commit()
        outsider_token = _token(outsider)

    patch_resp = client.patch(
        "/api/v1/tasks/task-authz-1",
        json={"title": "Hijacked"},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert patch_resp.status_code == 403

    delete_resp = client.delete(
        "/api/v1/tasks/task-authz-1",
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert delete_resp.status_code == 403

    with app.app_context():
        # Confirm the task was genuinely untouched, not just a bad response code.
        task = db.session.get(Task, "task-authz-1")
        assert task.title == "Secret task"


def test_non_member_cannot_create_workspace_under_org_they_dont_belong_to(app, client, db):
    from app.organizations.models import Organization

    with app.app_context():
        founder = _make_user("founder@example.com")
        outsider = _make_user("orgoutsider@example.com")
        org = Organization(name="Acme Inc", owner_id=founder.id)
        db.session.add(org)
        db.session.commit()
        org_id = org.id
        outsider_token = _token(outsider)

    resp = client.post(
        "/api/v1/workspaces",
        json={"workspace": {"name": "Hostile takeover", "context": "company", "organizationId": org_id}},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


def test_user_cannot_enumerate_another_users_workspace_list(app, client, db):
    with app.app_context():
        victim = _make_user("victim@example.com")
        attacker = _make_user("attacker@example.com")
        attacker_token = _token(attacker)
        victim_id = victim.id

    resp = client.get(
        f"/api/v1/users/{victim_id}/workspaces",
        headers={"Authorization": f"Bearer {attacker_token}"},
    )
    assert resp.status_code == 403
