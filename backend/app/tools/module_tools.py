"""
Module marketplace business logic — shared by REST routes (app/modules/routes.py) and
MCP (app/mcp_server.py), same {"success", "data", "error"} convention as task_tools.py.
"""
import re
import threading
import uuid
from typing import Optional

from .task_tools import _ok, _fail, _get_db, _get_models


def _slugify(title: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return slug or str(uuid.uuid4())[:8]


def list_modules(category: Optional[str] = None, published_only: bool = True) -> dict:
    m = _get_models()
    q = m.ModuleTemplate.query
    if published_only:
        q = q.filter_by(is_published=True)
    if category:
        q = q.filter_by(category=category)
    templates = q.order_by(m.ModuleTemplate.install_count.desc()).all()
    return _ok([{
        "id": t.id, "title": t.title, "slug": t.slug, "description": t.description,
        "category": t.category, "difficulty": t.difficulty, "source": t.source,
        "isPublished": t.is_published, "installCount": t.install_count,
        "metadata": t.module_metadata,
    } for t in templates])


def get_module(module_template_id: str) -> dict:
    db = _get_db()
    m = _get_models()
    template = db.session.get(m.ModuleTemplate, module_template_id)
    if not template:
        return _fail(f"Module {module_template_id} not found")
    version = db.session.get(m.ModuleTemplateVersion, template.current_version_id) if template.current_version_id else None
    return _ok({
        "id": template.id, "title": template.title, "slug": template.slug,
        "description": template.description, "category": template.category,
        "difficulty": template.difficulty, "isPublished": template.is_published,
        "installCount": template.install_count,
        "structure": version.structure_json if version else None,
        "generationStatus": version.generation_status if version else None,
    })


def create_module_draft(title: str, description: str, category: str, difficulty: str, author_id: str) -> dict:
    """Creates the ModuleTemplate + a version row in 'pending' state. Generation itself
    runs async (see start_generation) so this returns immediately with an id to poll."""
    db = _get_db()
    m = _get_models()

    template = m.ModuleTemplate(
        id=str(uuid.uuid4()), title=title, slug=_slugify(title), description=description,
        category=category, difficulty=difficulty, source='ai_generated',
        author_id=author_id, is_published=False,
    )
    db.session.add(template)
    db.session.flush()

    version = m.ModuleTemplateVersion(
        id=str(uuid.uuid4()), module_template_id=template.id, version=1,
        structure_json={}, generated_by='gemini', generation_status='pending',
    )
    db.session.add(version)
    db.session.flush()  # version must exist before template's FK to it is set

    template.current_version_id = version.id
    db.session.commit()

    return _ok({"moduleTemplateId": template.id, "moduleTemplateVersionId": version.id, "status": "pending"})


def start_generation(app, module_template_id: str, module_template_version_id: str, goal: str, category: str, difficulty: str) -> None:
    """Kicks off generation on a background thread. No task-queue infra exists yet
    (no Celery/Redis) — a background thread + status polling is the deliberate Phase-1
    scope per the roadmap; revisit with a real queue if generation volume grows."""

    def _run():
        with app.app_context():
            from ..core.extensions import db
            from .. import models as m
            from ..modules.generation import run_generation

            version = db.session.get(m.ModuleTemplateVersion, module_template_version_id)
            if version:
                version.generation_status = 'generating'
                db.session.commit()
            try:
                run_generation(module_template_version_id, goal, category, difficulty)
            except Exception as e:
                version = db.session.get(m.ModuleTemplateVersion, module_template_version_id)
                if version:
                    version.generation_status = 'failed'
                    version.generation_error = str(e)
                    db.session.commit()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()


def get_generation_progress_by_template(module_template_id: str) -> dict:
    db = _get_db()
    m = _get_models()
    template = db.session.get(m.ModuleTemplate, module_template_id)
    if not template or not template.current_version_id:
        return _fail(f"Module {module_template_id} not found")
    return get_generation_progress(template.current_version_id)


def get_generation_progress(module_template_version_id: str) -> dict:
    db = _get_db()
    m = _get_models()
    version = db.session.get(m.ModuleTemplateVersion, module_template_version_id)
    if not version:
        return _fail(f"Module version {module_template_version_id} not found")
    milestones = (version.structure_json or {}).get("milestones", [])
    return _ok({
        "moduleTemplateVersionId": version.id,
        "status": version.generation_status,
        "error": version.generation_error,
        "milestoneCount": len(milestones),
        "taskCount": sum(len(ms.get("tasks", [])) for ms in milestones),
    })


def update_module_structure(module_template_id: str, milestones: list) -> dict:
    """Overwrites a module's draft structure_json before install — the review/edit step.
    Only allowed while the current version's generation_status is 'ready' (i.e. generation
    finished but nothing has been installed from it yet); editing a still-generating or
    already-failed version doesn't make sense."""
    db = _get_db()
    m = _get_models()

    template = db.session.get(m.ModuleTemplate, module_template_id)
    if not template or not template.current_version_id:
        return _fail(f"Module {module_template_id} not found")
    version = db.session.get(m.ModuleTemplateVersion, template.current_version_id)
    if not version:
        return _fail(f"Module {module_template_id} not found")
    if version.generation_status != 'ready':
        return _fail(f"Module structure can only be edited once generation is ready (current status: {version.generation_status})")

    if not isinstance(milestones, list):
        return _fail("milestones must be a list")
    for ms in milestones:
        if not isinstance(ms, dict) or not ms.get('title'):
            return _fail("Each milestone requires a title")
        tasks = ms.get('tasks', [])
        if not isinstance(tasks, list):
            return _fail("Each milestone's tasks must be a list")
        for t in tasks:
            if not isinstance(t, dict) or not t.get('title'):
                return _fail("Each task requires a title")

    version.structure_json = {"milestones": milestones}
    db.session.commit()

    return _ok({
        "id": template.id,
        "structure": version.structure_json,
        "milestoneCount": len(milestones),
        "taskCount": sum(len(ms.get('tasks', [])) for ms in milestones),
    })


def publish_module(module_template_id: str) -> dict:
    db = _get_db()
    m = _get_models()
    template = db.session.get(m.ModuleTemplate, module_template_id)
    if not template:
        return _fail(f"Module {module_template_id} not found")
    version = db.session.get(m.ModuleTemplateVersion, template.current_version_id) if template.current_version_id else None
    if not version or version.generation_status != 'ready':
        return _fail("Module's current version is not ready to publish")
    template.is_published = True
    db.session.commit()
    return _ok({"id": template.id, "status": "published"})


def install_module(module_template_id: str, workspace_id: str, owner_id: str, company_id: Optional[str] = None) -> dict:
    """Fans a ready ModuleTemplateVersion's structure_json out into a real
    Project + Milestone + Task graph, tagged via Task.module_instance_id, so
    AgileBoard/ScheduleView render it with zero module-specific code."""
    db = _get_db()
    m = _get_models()

    template = db.session.get(m.ModuleTemplate, module_template_id)
    if not template:
        return _fail(f"Module {module_template_id} not found")
    version = db.session.get(m.ModuleTemplateVersion, template.current_version_id) if template.current_version_id else None
    if not version or version.generation_status != 'ready':
        return _fail("Module is not ready to install")

    workspace = db.session.get(m.Workspace, workspace_id)
    if not workspace:
        return _fail(f"Workspace {workspace_id} not found")

    instance = m.ModuleInstance(
        id=str(uuid.uuid4()), module_template_id=template.id,
        module_template_version_id=version.id, workspace_id=workspace_id,
        owner_id=owner_id, status='installing',
    )
    db.session.add(instance)
    db.session.flush()

    # get_full_state only nests projects under a Company, so an installed module's
    # project needs a home. If the caller picked an existing Initiative (Company),
    # use it — validated to belong to this workspace. Otherwise fall back to a
    # find-or-create "Modules" initiative per workspace, as before.
    modules_company = None
    if company_id:
        modules_company = db.session.get(m.Company, company_id)
        if not modules_company or modules_company.workspace_id != workspace_id:
            return _fail(f"Initiative {company_id} not found in this workspace")
    if not modules_company:
        modules_company = m.Company.query.filter_by(workspace_id=workspace_id, name='Modules').first()
    if not modules_company:
        modules_company = m.Company(
            id=str(uuid.uuid4()), workspace_id=workspace_id, name='Modules',
            mission='AI-generated learning and execution modules', color='indigo', whiteboard=[],
        )
        db.session.add(modules_company)
        db.session.flush()

    project = m.Project(
        id=str(uuid.uuid4()), workspace_id=workspace_id, company_id=modules_company.id,
        name=template.title, type='learning', mission=template.description or '',
        progress=0, whiteboard=[],
    )
    db.session.add(project)
    db.session.flush()
    instance.project_id = project.id

    # get_full_state additionally requires workspace-owner or ProjectMember to see a
    # project's tasks — grant the installer explicit access so non-owner members can too.
    db.session.add(m.ProjectMember(project_id=project.id, user_id=owner_id, role='owner'))

    milestones = (version.structure_json or {}).get("milestones", [])
    total_tasks = 0
    for m_idx, milestone_spec in enumerate(milestones):
        milestone = m.Milestone(
            id=str(uuid.uuid4()), project_id=project.id,
            title=milestone_spec.get('title', f'Milestone {m_idx + 1}'),
            description=milestone_spec.get('description', ''),
            status='pending', order=m_idx,
        )
        db.session.add(milestone)
        db.session.flush()

        for task_spec in milestone_spec.get('tasks', []):
            task = m.Task(
                id=str(uuid.uuid4()), workspace_id=workspace_id, project_id=project.id,
                title=task_spec.get('title', 'Untitled Task'),
                description=task_spec.get('description', ''),
                status='todo', priority=task_spec.get('priority', 'medium'),
                estimated_hours=task_spec.get('estimated_hours', 2.0),
                is_daily_focus=False, resources=[],
                milestone_id=milestone.id, module_instance_id=instance.id,
            )
            db.session.add(task)
            total_tasks += 1

    instance.status = 'active'
    template.install_count = (template.install_count or 0) + 1
    db.session.commit()

    return _ok({
        "moduleInstanceId": instance.id, "projectId": project.id,
        "milestoneCount": len(milestones), "taskCount": total_tasks, "status": "active",
    })


def get_module_instance(module_instance_id: str) -> dict:
    db = _get_db()
    m = _get_models()
    instance = db.session.get(m.ModuleInstance, module_instance_id)
    if not instance:
        return _fail(f"Module instance {module_instance_id} not found")

    tasks = m.Task.query.filter_by(module_instance_id=instance.id).all()
    done = sum(1 for t in tasks if t.status == 'done')
    progress = round((done / len(tasks)) * 100) if tasks else 0
    if instance.progress_pct != progress:
        instance.progress_pct = progress
        db.session.commit()

    return _ok({
        "id": instance.id, "moduleTemplateId": instance.module_template_id,
        "projectId": instance.project_id, "status": instance.status,
        "progressPct": progress, "totalTasks": len(tasks), "completedTasks": done,
    })
