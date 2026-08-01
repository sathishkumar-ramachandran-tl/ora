from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Workspace, Organization, WorkspaceMember
from ..extensions import db

workspace_api_bp = Blueprint('workspace_api', __name__)

@workspace_api_bp.route('/', methods=['POST'])
@jwt_required()
def create_workspace():
    """
    Create a Workspace.
    context: 'personal' | 'company'
    type: 'study' | 'project'
    """
    uid = get_jwt_identity()
    data = request.json
    
    context = data.get('context', 'personal')
    ws_type = data.get('type', 'project')
    name = data.get('name')
    org_id = data.get('organization_id')
    
    if not name:
        return jsonify({"error": "Name is required"}), 400
        
    if context == 'company' and not org_id:
        return jsonify({"error": "Organization ID required for company workspace"}), 400

    ws = Workspace(
        name=name,
        context=context,
        type=ws_type,
        owner_id=uid if context == 'personal' else None,
        organization_id=org_id if context == 'company' else None,
        persona=data.get('persona', 'general'),
        description=data.get('description')
    )
    
    db.session.add(ws)
    db.session.commit()
    
    # Add creator as admin member
    member = WorkspaceMember(
        workspace_id=ws.id,
        user_id=uid,
        role_id='admin' # Simplify for now
    )
    db.session.add(member)
    db.session.commit()
    
    return jsonify({
        "message": "Workspace created",
        "id": ws.id,
        "type": ws.type,
        "context": ws.context
    }), 201

@workspace_api_bp.route('/', methods=['GET'])
@jwt_required()
def list_workspaces():
    """
    Get all workspaces for user.
    Supports filtering by context (personal/company) via query param.
    """
    uid = get_jwt_identity()
    context_filter = request.args.get('context')
    
    # Simple query: join via membership
    query = db.session.query(Workspace).join(
        WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id
    ).filter(WorkspaceMember.user_id == uid)
    
    if context_filter:
        query = query.filter(Workspace.context == context_filter)
        
    workspaces = query.all()
    
    return jsonify([{
        "id": w.id,
        "name": w.name,
        "context": w.context,
        "type": w.type,
        "organization_id": w.organization_id
    } for w in workspaces])
