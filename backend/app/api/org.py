from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from ..models import Organization, OrganizationMember, User, Workspace
from ..extensions import db
import uuid
from datetime import datetime

org_bp = Blueprint('org', __name__)

@org_bp.route('/', methods=['POST'])
@jwt_required()
def create_organization():
    """
    Create a new Company/Organization.
    The creator becomes the owner and first admin.
    """
    uid = get_jwt_identity()
    data = request.json
    
    name = data.get('name')
    if not name:
        return jsonify({"error": "Organization name is required"}), 400
        
    org = Organization(
        name=name,
        domain=data.get('domain'),
        owner_id=uid,
        settings=data.get('settings', {})
    )
    
    db.session.add(org)
    db.session.flush()
    
    # Add creator as Owner in members table
    member = OrganizationMember(
        organization_id=org.id,
        user_id=uid,
        role='owner',
        status='active'
    )
    db.session.add(member)
    db.session.commit()
    
    return jsonify({
        "message": "Organization created successfully",
        "organization": {
            "id": org.id,
            "name": org.name,
            "role": "owner"
        }
    }), 201

@org_bp.route('/', methods=['GET'])
@jwt_required()
def get_my_organizations():
    """List organizations the user belongs to."""
    uid = get_jwt_identity()
    
    # Join OrganizationMember to find orgs
    memberships = OrganizationMember.query.filter_by(user_id=uid).all()
    
    results = []
    for m in memberships:
        org = Organization.query.get(m.organization_id)
        if org:
            results.append({
                "id": org.id,
                "name": org.name,
                "domain": org.domain,
                "role": m.role
            })
            
    return jsonify(results)

# --- ADMIN CONSOLE ROUTES ---

def is_org_admin(uid, org_id):
    member = OrganizationMember.query.filter_by(organization_id=org_id, user_id=uid).first()
    return member and member.role in ['owner', 'admin']

@org_bp.route('/<org_id>/dashboard', methods=['GET'])
@jwt_required()
def get_org_dashboard(org_id):
    """Get high-level stats for the Admin Console"""
    uid = get_jwt_identity()
    if not is_org_admin(uid, org_id):
        return jsonify({"error": "Unauthorized"}), 403
        
    member_count = OrganizationMember.query.filter_by(organization_id=org_id).count()
    workspace_count = Workspace.query.filter_by(organization_id=org_id).count()
    
    # Get recent members
    recent_members = db.session.query(User, OrganizationMember).join(
        OrganizationMember, User.id == OrganizationMember.user_id
    ).filter(OrganizationMember.organization_id == org_id).order_by(OrganizationMember.joined_at.desc()).limit(5).all()
    
    recent_members_json = [{
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": m.role,
        "status": m.status
    } for u, m in recent_members]
    
    return jsonify({
        "stats": {
            "totalMembers": member_count,
            "totalWorkspaces": workspace_count,
            "activeProjects": 0 # Placeholder for now, requires complex join
        },
        "recentMembers": recent_members_json
    })

@org_bp.route('/<org_id>/members', methods=['GET'])
@jwt_required()
def list_org_members(org_id):
    uid = get_jwt_identity()
    if not is_org_admin(uid, org_id):
        return jsonify({"error": "Unauthorized"}), 403
        
    members = db.session.query(User, OrganizationMember).join(
        OrganizationMember, User.id == OrganizationMember.user_id
    ).filter(OrganizationMember.organization_id == org_id).all()
    
    return jsonify([{
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": m.role,
        "status": m.status,
        "joinedAt": m.joined_at.isoformat()
    } for u, m in members])

@org_bp.route('/<org_id>/members', methods=['POST'])
@jwt_required()
def invite_member(org_id):
    uid = get_jwt_identity()
    if not is_org_admin(uid, org_id):
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.json
    email = data.get('email')
    role = data.get('role', 'member')
    
    if not email:
        return jsonify({"error": "Email required"}), 400
        
    # Check if user exists
    user = User.query.filter_by(email=email).first()
    if not user:
        # Create user (invited state)
        user = User(email=email, name=email.split('@')[0], is_onboarded=False)
        db.session.add(user)
        db.session.flush()
        
    # Check existing membership
    existing = OrganizationMember.query.filter_by(organization_id=org_id, user_id=user.id).first()
    if existing:
        return jsonify({"error": "User already in organization"}), 400
        
    new_member = OrganizationMember(
        organization_id=org_id,
        user_id=user.id,
        role=role,
        status='invited'
    )
    db.session.add(new_member)
    db.session.commit()
    
    return jsonify({"message": "User invited", "member": {
        "id": user.id,
        "email": user.email,
        "role": role,
        "status": 'invited'
    }}), 201

@org_bp.route('/<org_id>/members/<user_id>', methods=['PUT'])
@jwt_required()
def update_member_role(org_id, user_id):
    uid = get_jwt_identity()
    if not is_org_admin(uid, org_id):
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.json
    new_role = data.get('role')
    
    member = OrganizationMember.query.filter_by(organization_id=org_id, user_id=user_id).first()
    if not member:
        return jsonify({"error": "Member not found"}), 404
        
    # Prevent self-demotion of owner if they are the only owner (add logic for prod)
    member.role = new_role
    db.session.commit()
    
    return jsonify({"status": "updated"})

