from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..auth.models import User
from .models import Workspace, WorkspaceMember

workspace_bp = Blueprint('workspace', __name__)


@workspace_bp.route('/workspaces', methods=['POST'])
@jwt_required()
def create_workspace():
    """
    Create a Workspace.
    context: 'personal' | 'company' — company workspaces require organization_id.
    type: 'study' | 'project'
    """
    from ..projects.models import Company

    user_id = get_jwt_identity()
    data = request.json or {}
    ws_data = data.get('workspace', data)  # accept either {workspace: {...}} or a flat body

    context = ws_data.get('context', 'personal')
    organization_id = ws_data.get('organizationId') or ws_data.get('organization_id')
    if context == 'company' and not organization_id:
        return jsonify({"error": "organization_id is required for a company workspace"}), 400

    if context == 'company':
        from ..organizations.permissions import check_permission
        if not check_permission(user_id, organization_id, 'workspace.create'):
            return jsonify({"error": "You don't have permission to create a workspace in this organization"}), 403

    from ..billing import service as billing_service
    sub = billing_service.get_subscription(
        user_id=user_id if context == 'personal' else None,
        organization_id=organization_id if context == 'company' else None,
    )
    if not sub:
        sub = billing_service.create_trial_subscription(
            user_id=user_id if context == 'personal' else None,
            organization_id=organization_id if context == 'company' else None,
        )
    limit_check = billing_service.check_limit(sub, 'workspaces')
    if not limit_check['allowed']:
        return jsonify({
            "error": f"Workspace limit reached for your plan ({limit_check['current']}/{limit_check['limit']}). Upgrade to create more.",
            "code": "limit_reached",
            "resource": "workspaces",
        }), 402

    ws = Workspace(
        id=ws_data.get('id'),
        name=ws_data['name'],
        type=ws_data.get('type', 'project'),
        context=context,
        persona=ws_data.get('persona', 'general'),
        owner_id=user_id if context == 'personal' else None,
        organization_id=organization_id if context == 'company' else None,
        description=ws_data.get('description'),
        company_website=ws_data.get('companyWebsite'),
        location=ws_data.get('location'),
        employee_count=ws_data.get('employeeCount'),
        category=ws_data.get('category'),
        ai_context_description=ws_data.get('aiContextDescription'),
    )
    db.session.add(ws)
    db.session.flush()

    db.session.add(WorkspaceMember(workspace_id=ws.id, user_id=user_id, role_id='owner'))
    db.session.flush()

    if ws.type == 'study' or context == 'personal':
        db.session.add(Company(workspace_id=ws.id, name='General', mission='General tasks', color='slate'))

    db.session.commit()
    return jsonify({"status": "created", "id": ws.id, "type": ws.type, "context": ws.context}), 201


@workspace_bp.route('/users/<user_id>/workspaces', methods=['GET'])
@jwt_required()
def get_user_workspaces(user_id):
    if user_id != get_jwt_identity():
        return jsonify({"error": "Forbidden"}), 403

    memberships = WorkspaceMember.query.filter_by(user_id=user_id).all()
    workspaces = []
    for m in memberships:
        ws = db.session.get(Workspace, m.workspace_id)
        if ws:
            workspaces.append({
                "id": ws.id, "name": ws.name, "type": ws.type, "context": ws.context,
                "persona": ws.persona, "organizationId": ws.organization_id, "role": m.role_id,
            })
    return jsonify(workspaces)


@workspace_bp.route('/workspaces/<ws_id>/full-state', methods=['GET'])
@jwt_required()
def get_full_state(ws_id):
    from ..projects.models import Company, Project, ProjectMember
    from ..tasks.models import Task

    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    is_member = WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=current_user).first() is not None
    if not is_member and workspace.owner_id != current_user:
        return jsonify({"error": "Forbidden"}), 403

    companies = Company.query.filter_by(workspace_id=ws_id).all()
    result = []

    for c in companies:
        projects = Project.query.filter_by(company_id=c.id).all()
        c_data = {
            "id": c.id, "workspaceId": c.workspace_id, "name": c.name, "mission": c.mission,
            "color": c.color, "whiteboard": c.whiteboard, "projects": []
        }
        for p in projects:
            is_owner = workspace and workspace.owner_id == current_user
            has_project_access = ProjectMember.query.filter_by(project_id=p.id, user_id=current_user).first() is not None

            if is_member or is_owner or has_project_access:
                tasks = Task.query.filter_by(project_id=p.id).all()
                c_data['projects'].append({
                    "id": p.id, "workspaceId": p.workspace_id, "companyId": p.company_id,
                    "name": p.name, "type": p.type, "mission": p.mission, "progress": p.progress,
                    "whiteboard": p.whiteboard,
                    "tasks": [{
                        "id": t.id, "workspaceId": t.workspace_id, "title": t.title,
                        "description": t.description, "status": t.status, "priority": t.priority,
                        "estimatedHours": t.estimated_hours, "isDailyFocus": t.is_daily_focus,
                        "resources": t.resources,
                        "dueDate": t.due_date.isoformat() if t.due_date else None,
                        "labels": t.labels or [], "assigneeId": t.assignee_id,
                        "issueType": t.issue_type or "task",
                        "projectId": t.project_id, "milestoneId": t.milestone_id,
                        "sprintId": t.sprint_id, "parentTaskId": t.parent_task_id,
                    } for t in tasks]
                })
        result.append(c_data)

    return jsonify(result)


@workspace_bp.route('/workspaces/<ws_id>/home', methods=['GET'])
@jwt_required()
def get_workspace_home(ws_id):
    from ..agents.execution_context import ExecutionContext, execution_context
    from ..agents.adaptation import execution_signal_audit, plan_health, retrieval_benchmark
    from ..agents.models import PlanProposal, PlanRevisionProposal, ScheduleProposal
    from ..agents.planning import serialize_plan
    from ..agents.replanning import serialize_revision
    from ..agents.schedule_metrics import schedule_metrics
    from ..agents.scheduling import serialize_schedule
    from ..agents.today import recommend_today, today_calendar_summary
    from ..core.authz import user_can_access_workspace
    from ..projects.models import Project
    from ..tasks.models import Task

    current_user = get_jwt_identity()
    if not user_can_access_workspace(current_user, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    overrides = {
        "available_minutes": request.args.get("availableMinutes") or request.args.get("available_minutes"),
        "exclude_terms": request.args.getlist("exclude"),
        "prefer_terms": request.args.getlist("prefer"),
    }
    ctx = ExecutionContext(
        request_id=getattr(g, "request_id", None),
        user_id=current_user,
        workspace_id=ws_id,
        session_id=None,
        run_id=None,
        scope_level="workspace",
    )
    with execution_context(ctx):
        today = recommend_today(ctx, overrides)
        calendar = today_calendar_summary(ctx)
        scheduling_metrics = schedule_metrics(ctx)
        health = plan_health(ctx)
        signals = execution_signal_audit(ctx)
        retrieval = retrieval_benchmark(ctx)

    projects = Project.query.filter_by(workspace_id=ws_id).order_by(Project.progress.asc()).limit(6).all()
    active_projects = []
    for project in projects:
        total = Task.query.filter_by(project_id=project.id).count()
        done = Task.query.filter_by(project_id=project.id, status="done").count()
        active_projects.append({
            "id": project.id,
            "name": project.name,
            "type": project.type,
            "progress": project.progress,
            "task_count": total,
            "done_count": done,
        })

    pending_plan = PlanProposal.query.filter(
        PlanProposal.workspace_id == ws_id,
        PlanProposal.status.in_(["READY", "REVIEWING", "WAITING_FOR_CONFIRMATION"]),
    ).order_by(PlanProposal.created_at.desc()).first()
    pending_revision = PlanRevisionProposal.query.filter_by(
        workspace_id=ws_id,
        status="PROPOSED",
    ).order_by(PlanRevisionProposal.created_at.desc()).first()
    pending_schedule = ScheduleProposal.query.filter(
        ScheduleProposal.workspace_id == ws_id,
        ScheduleProposal.status.in_(["READY", "INFEASIBLE"]),
    ).order_by(ScheduleProposal.created_at.desc()).first()

    alerts = []
    if today.get("now") and today["now"].get("mastery_reason"):
        alerts.append({"type": "mastery_review", "message": today["now"]["mastery_reason"]})
    if pending_revision:
        alerts.append({"type": "plan_revision", "message": "A plan update is waiting for review."})
    if pending_schedule:
        alerts.append({"type": "schedule_proposal", "message": "A schedule proposal is waiting for review."})
    if health["status"] != "HEALTHY":
        alerts.append({"type": "plan_health", "message": health["reasons"][0]})

    return jsonify({
        "workspace": {"id": ws_id},
        "today": today,
        "calendar": calendar,
        "active_projects": active_projects,
        "pending_plan": serialize_plan(pending_plan) if pending_plan else None,
        "pending_revision": serialize_revision(pending_revision) if pending_revision else None,
        "pending_schedule": serialize_schedule(pending_schedule) if pending_schedule else None,
        "scheduling_metrics": scheduling_metrics,
        "plan_health": health,
        "execution_signals": signals,
        "retrieval_benchmark": retrieval,
        "alerts": alerts,
    })


@workspace_bp.route('/workspaces/<ws_id>/search', methods=['GET'])
@jwt_required()
def search_workspace(ws_id):
    from ..agents.models import Concept, PlanProposal
    from ..core.authz import user_can_access_workspace
    from ..projects.models import Project
    from ..tasks.models import Task

    current_user = get_jwt_identity()
    if not user_can_access_workspace(current_user, ws_id):
        return jsonify({"error": "Forbidden"}), 403
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify({"query": q, "results": []})
    like = f"%{q}%"
    results = []
    for project in Project.query.filter(Project.workspace_id == ws_id, Project.name.ilike(like)).limit(5).all():
        results.append({"type": "project", "id": project.id, "title": project.name, "subtitle": project.mission, "scope": {"level": "project", "projectId": project.id}})
    for task in Task.query.filter(Task.workspace_id == ws_id, Task.title.ilike(like)).limit(8).all():
        results.append({"type": "task", "id": task.id, "title": task.title, "subtitle": task.status, "scope": {"level": "task", "taskId": task.id, "projectId": task.project_id}})
    for plan in PlanProposal.query.filter(PlanProposal.workspace_id == ws_id, PlanProposal.title.ilike(like)).limit(5).all():
        results.append({"type": "plan", "id": plan.id, "title": plan.title, "subtitle": plan.status, "scope": {"level": plan.scope_level, "projectId": plan.scope_project_id, "taskId": plan.scope_task_id}})
    for concept in Concept.query.filter(Concept.workspace_id == ws_id, Concept.canonical_name.ilike(like)).limit(8).all():
        results.append({"type": "concept", "id": concept.id, "title": concept.canonical_name, "subtitle": concept.domain, "conceptKey": concept.concept_key})
    return jsonify({"query": q, "results": results[:20]})


@workspace_bp.route('/workspaces/<ws_id>/assessments', methods=['POST'])
@jwt_required()
def create_assessment_evidence(ws_id):
    from ..agents.coverage import infer_domain
    from ..agents.execution_context import ExecutionContext, execution_context
    from ..agents.mastery import record_competency_evidence, serialize_mastery
    from ..agents.adaptation import adapt_from_signal, signal_from_mastery
    from ..core.authz import user_can_access_workspace

    current_user = get_jwt_identity()
    if not user_can_access_workspace(current_user, ws_id):
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    concept_name = (data.get("concept_name") or data.get("conceptName") or "").strip()
    if not concept_name:
        return jsonify({"error": "conceptName is required"}), 400
    evidence_type = data.get("evidence_type") or data.get("evidenceType") or "assessment"
    result = data.get("result") or {}
    domain = data.get("domain") or infer_domain(concept_name)
    ctx = ExecutionContext(
        request_id=getattr(g, "request_id", None),
        user_id=current_user,
        workspace_id=ws_id,
        session_id=None,
        run_id=None,
        scope_level="workspace",
    )
    with execution_context(ctx):
        evidence, mastery = record_competency_evidence(
            ctx,
            concept_name=concept_name,
            domain=domain,
            evidence_type=evidence_type,
            result=result,
            strength=data.get("strength"),
            evidence_ref=data.get("evidence_ref") or data.get("evidenceRef"),
        )
        adaptation = adapt_from_signal(ctx, signal_from_mastery(mastery))
    return jsonify({
        "evidence": {
            "id": evidence.id,
            "evidence_type": evidence.evidence_type,
            "strength": evidence.strength,
            "result": evidence.result,
        },
        "mastery": serialize_mastery([mastery])[0],
        "adaptation": adaptation,
    }), 201


@workspace_bp.route('/workspaces/<ws_id>', methods=['PATCH'])
@jwt_required()
def update_workspace(ws_id):
    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can update settings"}), 403

    data = request.json or {}
    if data.get('name'): workspace.name = data['name']
    if data.get('companyWebsite') is not None: workspace.company_website = data['companyWebsite']
    if data.get('location') is not None: workspace.location = data['location']
    if data.get('employeeCount') is not None: workspace.employee_count = data['employeeCount']
    if data.get('aiContextDescription') is not None: workspace.ai_context_description = data['aiContextDescription']
    db.session.commit()
    return jsonify({"status": "updated"})


# --- Member management ---

@workspace_bp.route('/workspaces/<ws_id>/members', methods=['GET'])
@jwt_required()
def get_workspace_members(ws_id):
    current_user = get_jwt_identity()
    if not WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=current_user).first():
        return jsonify({"error": "Forbidden"}), 403

    members = WorkspaceMember.query.filter_by(workspace_id=ws_id).all()
    result = []
    for m in members:
        user = db.session.get(User, m.user_id)
        if user:
            result.append({
                # WorkspaceMember has a composite (workspace_id, user_id) primary key, not a
                # standalone id column — expose user_id as "id" so DELETE /members/<id> below
                # (scoped by ws_id in the URL already) can look it up directly.
                "id": m.user_id, "userId": m.user_id, "name": user.name,
                "email": user.email, "avatar": user.avatar, "role": m.role_id,
                "joinedAt": m.joined_at.isoformat() if m.joined_at else None,
            })
    return jsonify(result)


@workspace_bp.route('/workspaces/<ws_id>/invite', methods=['POST'])
@jwt_required()
def invite_to_workspace(ws_id):
    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can invite members"}), 403

    data = request.json or {}
    email = data.get('email')
    role = data.get('role', 'contributor')
    if not email:
        return jsonify({"error": "Email required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, name=email.split('@')[0])
        db.session.add(user)
        db.session.commit()

    if WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=user.id).first():
        return jsonify({"error": "User already in workspace"}), 400

    db.session.add(WorkspaceMember(workspace_id=ws_id, user_id=user.id, role_id=role))
    db.session.commit()
    return jsonify({"status": "invited", "userId": user.id}), 201


@workspace_bp.route('/workspaces/<ws_id>/members/<user_id>', methods=['DELETE'])
@jwt_required()
def remove_workspace_member(ws_id, user_id):
    current_user = get_jwt_identity()
    workspace = db.session.get(Workspace, ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only the workspace owner can remove members"}), 403

    member = WorkspaceMember.query.filter_by(workspace_id=ws_id, user_id=user_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404

    db.session.delete(member)
    db.session.commit()
    return jsonify({"status": "removed"}), 200
