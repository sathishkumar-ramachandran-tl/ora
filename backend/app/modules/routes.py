"""Module marketplace REST surface — browse/generate/publish/install, matching the
existing v2 blueprint convention (org_bp, billing_bp)."""
import logging

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity

from ..core.extensions import db
from ..core.authz import user_can_access_workspace
from ..tools import module_tools

logger = logging.getLogger(__name__)
module_bp = Blueprint('modules', __name__)


@module_bp.route('', methods=['GET'])
@jwt_required()
def browse_modules():
    category = request.args.get('category')
    result = module_tools.list_modules(category=category, published_only=True)
    return jsonify(result["data"])


@module_bp.route('/mine', methods=['GET'])
@jwt_required()
def my_modules():
    from .models import ModuleTemplate
    user_id = get_jwt_identity()
    templates = ModuleTemplate.query.filter_by(author_id=user_id).order_by(ModuleTemplate.created_at.desc()).all()
    return jsonify([{
        "id": t.id, "title": t.title, "category": t.category,
        "isPublished": t.is_published, "installCount": t.install_count,
    } for t in templates])


@module_bp.route('/<module_template_id>', methods=['GET'])
@jwt_required()
def get_module(module_template_id):
    result = module_tools.get_module(module_template_id)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 404
    return jsonify(result["data"])


@module_bp.route('', methods=['POST'])
@jwt_required()
def generate_module():
    """Kicks off async generation: creates the draft template+version synchronously,
    returns immediately with an id, generation runs on a background thread."""
    user_id = get_jwt_identity()
    data = request.json or {}
    goal = (data.get('goal') or '').strip()
    if not goal:
        return jsonify({"error": "goal is required"}), 400

    title = data.get('title') or goal[:80]
    category = data.get('category', 'general')
    difficulty = data.get('difficulty', 'intermediate')

    draft = module_tools.create_module_draft(
        title=title, description=goal, category=category,
        difficulty=difficulty, author_id=user_id,
    )
    if not draft["success"]:
        return jsonify({"error": draft["error"]}), 400

    module_tools.start_generation(
        current_app._get_current_object(),
        module_template_id=draft["data"]["moduleTemplateId"],
        module_template_version_id=draft["data"]["moduleTemplateVersionId"],
        goal=goal, category=category, difficulty=difficulty,
    )
    logger.info("module_generation_started", extra={
        "module_template_id": draft["data"]["moduleTemplateId"], "user_id": user_id,
    })
    return jsonify({**draft["data"], "status": "generating"}), 202


@module_bp.route('/<module_template_id>/progress', methods=['GET'])
@jwt_required()
def generation_progress(module_template_id):
    result = module_tools.get_generation_progress_by_template(module_template_id)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 404
    return jsonify(result["data"])


@module_bp.route('/<module_template_id>/structure', methods=['PATCH'])
@jwt_required()
def update_module_structure(module_template_id):
    """The review/edit step: overwrite a ready-but-not-installed draft's milestones/tasks
    before it's installed into a project. Only the module's author may edit it."""
    from .models import ModuleTemplate
    user_id = get_jwt_identity()
    template = db.session.get(ModuleTemplate, module_template_id)
    if not template:
        return jsonify({"error": "Module not found"}), 404
    if template.author_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    data = request.json or {}
    milestones = data.get('milestones')
    if milestones is None:
        return jsonify({"error": "milestones is required"}), 400

    result = module_tools.update_module_structure(module_template_id, milestones)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    logger.info("module_structure_updated", extra={"module_template_id": module_template_id, "user_id": user_id})
    return jsonify(result["data"])


@module_bp.route('/<module_template_id>/publish', methods=['POST'])
@jwt_required()
def publish_module(module_template_id):
    from .models import ModuleTemplate
    user_id = get_jwt_identity()
    template = db.session.get(ModuleTemplate, module_template_id)
    if not template:
        return jsonify({"error": "Module not found"}), 404
    if template.author_id != user_id:
        return jsonify({"error": "Forbidden"}), 403

    result = module_tools.publish_module(module_template_id)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    logger.info("module_published", extra={"module_template_id": module_template_id, "user_id": user_id})
    return jsonify(result["data"])


@module_bp.route('/<module_template_id>/install', methods=['POST'])
@jwt_required()
def install_module(module_template_id):
    user_id = get_jwt_identity()
    data = request.json or {}
    workspace_id = data.get('workspaceId')
    if not workspace_id:
        return jsonify({"error": "workspaceId is required"}), 400
    if not user_can_access_workspace(user_id, workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    result = module_tools.install_module(module_template_id, workspace_id, user_id, company_id=data.get('companyId'))
    if not result["success"]:
        return jsonify({"error": result["error"]}), 400
    logger.info("module_installed", extra={
        "module_template_id": module_template_id, "workspace_id": workspace_id, "user_id": user_id,
    })
    return jsonify(result["data"]), 201


@module_bp.route('/instances/<module_instance_id>', methods=['GET'])
@jwt_required()
def get_module_instance(module_instance_id):
    from .models import ModuleInstance
    user_id = get_jwt_identity()
    instance = db.session.get(ModuleInstance, module_instance_id)
    if not instance:
        return jsonify({"error": "Module instance not found"}), 404
    if not user_can_access_workspace(user_id, instance.workspace_id):
        return jsonify({"error": "Forbidden"}), 403

    result = module_tools.get_module_instance(module_instance_id)
    if not result["success"]:
        return jsonify({"error": result["error"]}), 404
    return jsonify(result["data"])
