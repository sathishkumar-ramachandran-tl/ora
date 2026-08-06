"""Module generation graph tests — mocked structured-output LLM calls (no live API key
needed), validating the outline -> expand -> critique -> materialize control flow and
the install fan-out into real Project/Milestone/Task rows."""
from unittest.mock import patch

from flask_jwt_extended import create_access_token

from app.core.extensions import db
from app.modules import generation
from app.modules.models import ModuleTemplate, ModuleTemplateVersion, ModuleInstance
from app.workspaces.models import Workspace
from app.auth.models import User
from app.tasks.models import Task
from app.projects.models import Milestone
from app.core.security import hash_password
from app.tools import module_tools


class _FakeStructuredModel:
    """Returned by `<model>.with_structured_output(schema)` — .invoke() ignores the
    prompt and returns a canned response keyed by which schema was requested."""

    def __init__(self, schema, responses):
        self.schema = schema
        self.responses = responses
        self.call_count = 0

    def invoke(self, messages):
        response = self.responses[self.schema.__name__]
        if callable(response):
            return response(self.call_count)
        self.call_count += 1
        return response


class _FakeModel:
    def __init__(self, responses):
        self.responses = responses

    def with_structured_output(self, schema):
        return _FakeStructuredModel(schema, self.responses)


def _outline():
    return generation.OutlineResult(milestones=[
        generation.MilestoneSpec(title="Foundations", description="Build the basics", order=0),
        generation.MilestoneSpec(title="Advanced Practice", description="Deepen skills", order=1),
    ])


def _tasks_for_milestone(n):
    return generation.MilestoneTasksResult(tasks=[
        generation.TaskSpec(title=f"Task {n}-1", description="", priority="medium", estimated_hours=2.0),
        generation.TaskSpec(title=f"Task {n}-2", description="", priority="high", estimated_hours=3.0),
    ])


def _make_draft():
    template = ModuleTemplate(
        id="tmpl-1", title="Test Module", slug="test-module", description="goal text",
        category="course", difficulty="intermediate", is_published=False,
    )
    db.session.add(template)
    db.session.flush()
    version = ModuleTemplateVersion(
        id="ver-1", module_template_id=template.id, version=1,
        structure_json={}, generated_by="gemini", generation_status="pending",
    )
    db.session.add(version)
    db.session.flush()
    template.current_version_id = version.id
    db.session.commit()
    return template, version


def test_generation_approves_first_pass_and_materializes(app, db):
    with app.app_context():
        template, version = _make_draft()

        counter = {"n": 0}

        def expand_response(_call_count):
            counter["n"] += 1
            return _tasks_for_milestone(counter["n"])

        fake_model = _FakeModel({
            "OutlineResult": _outline(),
            "MilestoneTasksResult": expand_response,
            "CritiqueResult": generation.CritiqueResult(approve=True, feedback="looks good"),
        })

        with patch.object(generation, "_pro_model", return_value=fake_model), \
             patch.object(generation, "_flash_model", return_value=fake_model):
            result = generation.run_generation(version.id, "goal text", "course", "intermediate")

        assert result["error"] is None
        assert result["approved"] is True
        assert len(result["milestones"]) == 2
        assert all(len(m["tasks"]) == 2 for m in result["milestones"])

        db.session.refresh(version)
        assert version.generation_status == "ready"
        assert len(version.structure_json["milestones"]) == 2


def test_generation_revises_then_gives_up_after_max_rounds(app, db):
    with app.app_context():
        template, version = _make_draft()

        counter = {"n": 0}

        def expand_response(_call_count):
            counter["n"] += 1
            return _tasks_for_milestone(counter["n"])

        fake_model = _FakeModel({
            "OutlineResult": _outline(),
            "MilestoneTasksResult": expand_response,
            "CritiqueResult": generation.CritiqueResult(approve=False, feedback="not good enough"),
        })

        with patch.object(generation, "_pro_model", return_value=fake_model), \
             patch.object(generation, "_flash_model", return_value=fake_model):
            result = generation.run_generation(version.id, "goal text", "course", "intermediate")

        # Never approved, but bounded by MAX_CRITIQUE_ROUNDS rather than looping forever.
        assert result["approved"] is False
        assert result["critique_round"] == generation.MAX_CRITIQUE_ROUNDS

        db.session.refresh(version)
        assert version.generation_status == "ready"  # materialized anyway once the bound is hit


def test_generation_records_failure_on_outline_error(app, db):
    with app.app_context():
        template, version = _make_draft()

        class BrokenModel:
            def with_structured_output(self, schema):
                class _Broken:
                    def invoke(self, messages):
                        raise RuntimeError("provider unavailable")
                return _Broken()

        with patch.object(generation, "_pro_model", return_value=BrokenModel()):
            result = generation.run_generation(version.id, "goal text", "course", "intermediate")

        assert result["error"] is not None
        db.session.refresh(version)
        assert version.generation_status == "failed"
        assert "provider unavailable" in version.generation_error


def test_install_module_fans_out_project_milestones_tasks(app, db):
    with app.app_context():
        user = User(id="user-mod-1", email="modinstall@example.com", name="Mod Install",
                    password_hash=hash_password("pw"), email_verified=True)
        db.session.add(user)
        ws = Workspace(id="ws-mod-1", name="Mod WS", context="personal", owner_id=user.id)
        db.session.add(ws)
        db.session.commit()

        template, version = _make_draft()
        version.structure_json = {
            "milestones": [
                {"title": "M1", "description": "", "order": 0, "tasks": [
                    {"title": "T1", "description": "", "priority": "medium", "estimated_hours": 1.0},
                    {"title": "T2", "description": "", "priority": "high", "estimated_hours": 2.0},
                ]},
            ]
        }
        version.generation_status = "ready"
        db.session.commit()

        result = module_tools.install_module(template.id, ws.id, user.id)
        assert result["success"], result["error"]
        assert result["data"]["taskCount"] == 2
        assert result["data"]["milestoneCount"] == 1

        instance = db.session.get(ModuleInstance, result["data"]["moduleInstanceId"])
        assert instance.status == "active"
        assert instance.project_id is not None

        tasks = Task.query.filter_by(module_instance_id=instance.id).all()
        assert len(tasks) == 2
        assert all(t.project_id == instance.project_id for t in tasks)

        milestones = Milestone.query.filter_by(project_id=instance.project_id).all()
        assert len(milestones) == 1

        # get_full_state only nests projects under a Company — confirm the installed
        # project actually surfaces there instead of being silently invisible.
        from app.projects.models import Company, Project
        project = db.session.get(Project, instance.project_id)
        assert project.company_id is not None
        company = db.session.get(Company, project.company_id)
        assert company.name == 'Modules'
        assert company.workspace_id == ws.id

        token = create_access_token(identity=user.id)

    resp = app.test_client().get(
        f"/api/v1/workspaces/{ws.id}/full-state",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    modules_company = next((c for c in resp.json if c["id"] == company.id), None)
    assert modules_company is not None
    assert any(p["id"] == instance.project_id for p in modules_company["projects"])


def test_install_module_uses_given_company_id(app, db):
    with app.app_context():
        from app.projects.models import Company

        user = User(id="user-mod-3", email="modinstall3@example.com", name="Mod Install 3",
                    password_hash=hash_password("pw"), email_verified=True)
        db.session.add(user)
        ws = Workspace(id="ws-mod-3", name="Mod WS 3", context="personal", owner_id=user.id)
        db.session.add(ws)
        db.session.commit()
        other_company = Company(id="co-mod-3", workspace_id=ws.id, name="My Initiative", mission="", color="blue", whiteboard=[])
        db.session.add(other_company)
        db.session.commit()

        template, version = _make_draft()
        version.structure_json = {"milestones": [{"title": "M1", "description": "", "order": 0, "tasks": [
            {"title": "T1", "description": "", "priority": "medium", "estimated_hours": 1.0},
        ]}]}
        version.generation_status = "ready"
        db.session.commit()

        result = module_tools.install_module(template.id, ws.id, user.id, company_id=other_company.id)
        assert result["success"], result["error"]

        from app.projects.models import Project
        project = db.session.get(Project, result["data"]["projectId"])
        assert project.company_id == other_company.id

        # A Company from a different workspace must be rejected, not silently used.
        no_modules_company = Company.query.filter_by(workspace_id=ws.id, name="Modules").first()
        assert no_modules_company is None


def test_install_module_rejects_company_from_other_workspace(app, db):
    with app.app_context():
        from app.projects.models import Company

        user = User(id="user-mod-4", email="modinstall4@example.com", name="Mod Install 4",
                    password_hash=hash_password("pw"), email_verified=True)
        db.session.add(user)
        ws = Workspace(id="ws-mod-4", name="Mod WS 4", context="personal", owner_id=user.id)
        other_ws = Workspace(id="ws-mod-4b", name="Mod WS 4b", context="personal", owner_id=user.id)
        db.session.add_all([ws, other_ws])
        db.session.commit()
        foreign_company = Company(id="co-mod-4", workspace_id=other_ws.id, name="Foreign", mission="", color="blue", whiteboard=[])
        db.session.add(foreign_company)
        db.session.commit()

        template, version = _make_draft()
        version.structure_json = {"milestones": [{"title": "M1", "description": "", "order": 0, "tasks": [
            {"title": "T1", "description": "", "priority": "medium", "estimated_hours": 1.0},
        ]}]}
        version.generation_status = "ready"
        db.session.commit()

        result = module_tools.install_module(template.id, ws.id, user.id, company_id=foreign_company.id)
        assert not result["success"]
        assert "not found" in result["error"].lower()


def test_install_module_rejects_when_not_ready(app, db):
    with app.app_context():
        user = User(id="user-mod-2", email="modinstall2@example.com", name="Mod Install 2",
                    password_hash=hash_password("pw"), email_verified=True)
        db.session.add(user)
        ws = Workspace(id="ws-mod-2", name="Mod WS 2", context="personal", owner_id=user.id)
        db.session.add(ws)
        db.session.commit()

        template, version = _make_draft()  # left at generation_status='pending'

        result = module_tools.install_module(template.id, ws.id, user.id)
        assert not result["success"]
        assert "not ready" in result["error"]


def test_full_rest_flow_generate_progress_publish_install(app, db, client):
    """End-to-end over HTTP: POST /api/v2/modules -> GET progress -> POST publish
    -> POST install, with generation forced synchronous (no real thread/LLM) so the
    test is deterministic."""
    with app.app_context():
        user = User(id="user-mod-3", email="modflow@example.com", name="Mod Flow",
                    password_hash=hash_password("pw"), email_verified=True)
        db.session.add(user)
        ws = Workspace(id="ws-mod-3", name="Mod WS 3", context="personal", owner_id=user.id)
        db.session.add(ws)
        db.session.commit()
        token = create_access_token(identity=user.id)

    fake_model = _FakeModel({
        "OutlineResult": _outline(),
        "MilestoneTasksResult": lambda n: _tasks_for_milestone(n),
        "CritiqueResult": generation.CritiqueResult(approve=True, feedback="ok"),
    })

    def _synchronous_start_generation(app_obj, module_template_id, module_template_version_id, goal, category, difficulty):
        with app_obj.app_context():
            with patch.object(generation, "_pro_model", return_value=fake_model), \
                 patch.object(generation, "_flash_model", return_value=fake_model):
                generation.run_generation(module_template_version_id, goal, category, difficulty)

    headers = {"Authorization": f"Bearer {token}"}

    with patch("app.modules.routes.module_tools.start_generation", side_effect=_synchronous_start_generation):
        resp = client.post("/api/v2/modules", json={
            "goal": "Learn GCP Data Engineering in 3 months",
            "category": "course", "difficulty": "intermediate",
        }, headers=headers)
    assert resp.status_code == 202
    module_id = resp.json["moduleTemplateId"]

    progress = client.get(f"/api/v2/modules/{module_id}/progress", headers=headers)
    assert progress.status_code == 200
    assert progress.json["status"] == "ready"
    assert progress.json["milestoneCount"] == 2

    publish = client.post(f"/api/v2/modules/{module_id}/publish", headers=headers)
    assert publish.status_code == 200
    assert publish.json["status"] == "published"

    browse = client.get("/api/v2/modules", headers=headers)
    assert browse.status_code == 200
    assert any(m["id"] == module_id for m in browse.json)

    install = client.post(f"/api/v2/modules/{module_id}/install", json={"workspaceId": "ws-mod-3"}, headers=headers)
    assert install.status_code == 201
    assert install.json["taskCount"] == 4

    instance_resp = client.get(f"/api/v2/modules/instances/{install.json['moduleInstanceId']}", headers=headers)
    assert instance_resp.status_code == 200
    assert instance_resp.json["status"] == "active"


def test_install_requires_workspace_membership(app, db, client):
    with app.app_context():
        owner = User(id="user-mod-4", email="modowner@example.com", name="Mod Owner",
                     password_hash=hash_password("pw"), email_verified=True)
        outsider = User(id="user-mod-5", email="modoutsider@example.com", name="Mod Outsider",
                         password_hash=hash_password("pw"), email_verified=True)
        db.session.add_all([owner, outsider])
        ws = Workspace(id="ws-mod-4", name="Mod WS 4", context="personal", owner_id=owner.id)
        db.session.add(ws)
        template, version = _make_draft()
        version.generation_status = "ready"
        version.structure_json = {"milestones": []}
        db.session.commit()
        outsider_token = create_access_token(identity=outsider.id)
        module_id = template.id

    resp = client.post(
        f"/api/v2/modules/{module_id}/install",
        json={"workspaceId": "ws-mod-4"},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert resp.status_code == 403


def test_update_module_structure_overwrites_draft(app, db):
    with app.app_context():
        template, version = _make_draft()
        version.generation_status = "ready"
        version.structure_json = {"milestones": [{"title": "Old", "description": "", "order": 0, "tasks": []}]}
        db.session.commit()

        new_milestones = [
            {"title": "Foundations", "description": "d", "order": 0, "tasks": [
                {"title": "Read docs", "description": "", "priority": "medium", "estimated_hours": 1.0},
            ]},
            {"title": "Practice", "description": "", "order": 1, "tasks": []},
        ]
        result = module_tools.update_module_structure(template.id, new_milestones)
        assert result["success"], result["error"]
        assert result["data"]["milestoneCount"] == 2
        assert result["data"]["taskCount"] == 1

        refreshed = db.session.get(ModuleTemplateVersion, version.id)
        assert refreshed.structure_json["milestones"][0]["title"] == "Foundations"


def test_update_module_structure_rejects_when_not_ready(app, db):
    with app.app_context():
        template, version = _make_draft()  # left at 'pending'
        result = module_tools.update_module_structure(template.id, [{"title": "X", "tasks": []}])
        assert not result["success"]
        assert "ready" in result["error"]


def test_update_module_structure_rejects_missing_titles(app, db):
    with app.app_context():
        template, version = _make_draft()
        version.generation_status = "ready"
        db.session.commit()

        result = module_tools.update_module_structure(template.id, [{"title": "", "tasks": []}])
        assert not result["success"]

        result2 = module_tools.update_module_structure(template.id, [
            {"title": "M1", "tasks": [{"title": ""}]},
        ])
        assert not result2["success"]


def test_update_module_structure_route_requires_author(app, db, client):
    with app.app_context():
        author = User(id="user-mod-6", email="modauthor@example.com", name="Author",
                      password_hash=hash_password("pw"), email_verified=True)
        outsider = User(id="user-mod-7", email="modoutsider2@example.com", name="Outsider",
                        password_hash=hash_password("pw"), email_verified=True)
        db.session.add_all([author, outsider])
        template, version = _make_draft()
        template.author_id = author.id
        version.generation_status = "ready"
        db.session.commit()
        outsider_token = create_access_token(identity=outsider.id)
        author_token = create_access_token(identity=author.id)
        module_id = template.id

    forbidden = client.patch(
        f"/api/v2/modules/{module_id}/structure",
        json={"milestones": [{"title": "M1", "tasks": []}]},
        headers={"Authorization": f"Bearer {outsider_token}"},
    )
    assert forbidden.status_code == 403

    ok = client.patch(
        f"/api/v2/modules/{module_id}/structure",
        json={"milestones": [{"title": "M1", "tasks": []}]},
        headers={"Authorization": f"Bearer {author_token}"},
    )
    assert ok.status_code == 200
    assert ok.json["milestoneCount"] == 1
