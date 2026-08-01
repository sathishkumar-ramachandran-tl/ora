from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from .models import User, Workspace, WorkspaceMember, ProjectMember, Company, Project, Task, Note, ActivityLog, Document, CalendarEvent
from .extensions import db
# from flask_mail import Message # Removed for Gmail API
from datetime import datetime, timedelta
import random
import base64
from .services.ai_service import AIService
from .services.gmail_service import GmailService

auth_bp = Blueprint('auth', __name__)
workspace_bp = Blueprint('workspace', __name__)
agent_bp = Blueprint('agent', __name__)

# --- AUTH ROUTES ---

@auth_bp.route('/request-otp', methods=['POST'])
def request_otp():
    email = request.json.get('email')
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    # Generate OTP
    otp = f"{random.randint(100000, 999999)}"
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    user = User.query.filter_by(email=email).first()
    if not user:
        # Temporary create to store OTP, or handle in separate cache (Redis preferred in Prod)
        user = User(email=email)
        db.session.add(user)
    
    user.otp_code = otp
    user.otp_expiry = expiry
    db.session.commit()
    
    try:
        # GCP Gmail API Send
        gmail_service = GmailService()
        success = gmail_service.send_email(
            recipient=email,
            subject="Your OTP for Sindhai Cortex",
            body=f"Your OTP is {otp}. It expires in 10 minutes."
        )
        if not success:
            raise Exception("Gmail API returned False")
            
    except Exception as e:
        current_app.logger.error(f"Error sending email: {e}")
        # In prod, we typically want to return 500, but for dev debug we might want to know
        return jsonify({"error": "Failed to send OTP email via Gmail API"}), 500
    
    current_app.logger.info(f"OTP for {email}: {otp}") 
    
    return jsonify({"message": "OTP Sent", "debug_otp": otp}) # Debug OTP removed in real prod

@auth_bp.route('/verify-otp', methods=['POST'])
def verify_otp():
    email = request.json.get('email')
    code = request.json.get('code', '').strip() # Clean whitespace
    
    user = User.query.filter_by(email=email).first()
    if not user or user.otp_code != str(code) or datetime.utcnow() > user.otp_expiry:
        return jsonify({"error": "Invalid or expired OTP"}), 400
    
    # Clear OTP
    user.otp_code = None
    db.session.commit()
    
    access_token = create_access_token(identity=user.id)
    return jsonify({
        "token": access_token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar": user.avatar,
            "is_onboarded": user.is_onboarded
        }
    })

@auth_bp.route('/update-profile', methods=['POST'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.json
    
    if not data.get('name') and not user.name:
        return jsonify({"error": "Name is required"}), 400

    if data.get('name'): user.name = data['name']
    if data.get('gender') is not None: user.gender = data['gender']
    if data.get('phone') is not None: user.phone = data['phone']
    if data.get('age') is not None: user.age = data['age']
    if data.get('location') is not None: user.location = data['location']
    if data.get('country') is not None: user.country = data['country']
    if data.get('purpose') is not None: user.purpose = data['purpose']
    if data.get('is_onboarded'): user.is_onboarded = True

    db.session.commit()

    return jsonify({
        "message": "Profile updated successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "age": user.age,
            "location": user.location,
            "country": user.country,
            "purpose": user.purpose,
            "is_onboarded": user.is_onboarded
        }
    })

@auth_bp.route('/check-user', methods=['POST'])
def check_user():
    email = request.json.get('email')
    user = User.query.filter_by(email=email).first()
    if user and user.name:
        return jsonify({"exists": True, "user": {"id": user.id, "email": user.email, "name": user.name}})
    return jsonify({"exists": False})

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar": user.avatar,
        "phone": user.phone,
        "age": user.age,
        "location": user.location,
        "country": user.country,
        "purpose": user.purpose,
        "is_onboarded": user.is_onboarded
    })

# --- WORKSPACE ROUTES ---

@workspace_bp.route('/users', methods=['POST'])
def update_profile():
    data = request.json
    user = User.query.get(data['id'])
    is_new = False
    
    if not user:
        user = User(id=data['id'], email=data['email'])
        db.session.add(user)
        is_new = True
    
    user.name = data.get('name')
    user.avatar = data.get('avatar')
    
    # New Fields
    user.gender = data.get('gender', user.gender)
    user.phone = data.get('phone', user.phone)
    user.age = data.get('age', user.age)
    user.location = data.get('location', user.location)
    user.is_onboarded = True

    db.session.commit()
    
    if is_new:
        try:
           gmail_service = GmailService()
           gmail_service.send_welcome_email(user.email, user.name)
        except Exception as e:
           print(f"Failed to send welcome email: {e}")
           
    return jsonify({"status": "success"})

@workspace_bp.route('/workspaces', methods=['POST'])
@jwt_required()
def create_workspace():
    data = request.json
    ws_data = data['workspace']
    user_id = data['userId']
    
    ws = Workspace(
        id=ws_data['id'],
        name=ws_data['name'],
        type=ws_data['type'],
        context=ws_data.get('context', 'personal'), # Added context field
        persona=ws_data['persona'],
        owner_id=user_id,
        company_website=ws_data.get('companyWebsite'),
        location=ws_data.get('location'),
        employee_count=ws_data.get('employeeCount'),
        category=ws_data.get('category'),
        ai_context_description=ws_data.get('aiContextDescription')
    )

    db.session.add(ws)
    
    member = WorkspaceMember(workspace_id=ws.id, user_id=user_id, role_id='owner')
    db.session.add(member)
    
    # Flush here to ensure Workspace and Member exist before Company constraint checked
    db.session.flush() 
    
    if ws.type == 'personal':
        comp = Company(workspace_id=ws.id, name='General', mission='General tasks', color='slate')
        db.session.add(comp)
        
    db.session.commit()
    return jsonify({"status": "created"})

@workspace_bp.route('/users/<user_id>/workspaces', methods=['GET'])
@jwt_required()
def get_user_workspaces(user_id):
    memberships = WorkspaceMember.query.filter_by(user_id=user_id).all()
    workspaces = []
    for m in memberships:
        ws = Workspace.query.get(m.workspace_id)
        if ws:
            workspaces.append({
                "id": ws.id,
                "name": ws.name,
                "type": ws.type,
                "context": ws.context,
                "persona": ws.persona,
                "role": m.role_id
            })
    return jsonify(workspaces)

@workspace_bp.route('/workspaces/<ws_id>/full-state', methods=['GET'])
@jwt_required()
def get_full_state(ws_id):
    current_user = get_jwt_identity()
    companies = Company.query.filter_by(workspace_id=ws_id).all()
    result = []
    
    for c in companies:
        projects = Project.query.filter_by(company_id=c.id).all()
        c_data = {
            "id": c.id,
            "workspaceId": c.workspace_id,
            "name": c.name,
            "mission": c.mission,
            "color": c.color,
            "whiteboard": c.whiteboard,
            "projects": []
        }
        
        for p in projects:
            # Check if user has access to this project (is owner or assigned member)
            workspace = Workspace.query.get(ws_id)
            is_owner = workspace and workspace.owner_id == current_user
            has_project_access = ProjectMember.query.filter_by(
                project_id=p.id, user_id=current_user
            ).first() is not None
            
            # Only include project if user is owner or has explicit access
            if is_owner or has_project_access:
                tasks = Task.query.filter_by(project_id=p.id).all()
                p_data = {
                    "id": p.id,
                    "workspaceId": p.workspace_id,
                    "companyId": p.company_id,
                    "name": p.name,
                    "type": p.type,
                    "mission": p.mission,
                    "progress": p.progress,
                    "whiteboard": p.whiteboard,
                    "tasks": [{
                        "id": t.id,
                        "workspaceId": t.workspace_id,
                        "title": t.title,
                        "description": t.description,
                        "status": t.status,
                        "priority": t.priority,
                        "estimatedHours": t.estimated_hours,
                        "isDailyFocus": t.is_daily_focus,
                        "resources": t.resources,
                        "dueDate": t.due_date.isoformat() if t.due_date else None,
                        "labels": t.labels or [],
                        "assigneeId": t.assignee_id,
                        "issueType": t.issue_type or "task"
                    } for t in tasks]
                }
                c_data['projects'].append(p_data)
        result.append(c_data)
        
    return jsonify(result)

# --- WORKSPACE MEMBER MANAGEMENT ---

@workspace_bp.route('/workspaces/<ws_id>/members', methods=['GET'])
@jwt_required()
def get_workspace_members(ws_id):
    """Get all members of a workspace with their roles"""
    members = WorkspaceMember.query.filter_by(workspace_id=ws_id).all()
    result = []
    for m in members:
        user = User.query.get(m.user_id)
        if user:
            result.append({
                "id": m.id,
                "userId": m.user_id,
                "name": user.name,
                "email": user.email,
                "avatar": user.avatar,
                "role": m.role_id,
                "joinedAt": m.joined_at.isoformat() if m.joined_at else None
            })
    return jsonify(result)

@workspace_bp.route('/workspaces/<ws_id>/invite', methods=['POST'])
@jwt_required()
def invite_to_workspace(ws_id):
    """Invite a user to workspace (only workspace owner can invite)"""
    current_user = get_jwt_identity()
    workspace = Workspace.query.get(ws_id)
    
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    
    # Check if current user is workspace owner
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only workspace owner can invite members"}), 403
    
    data = request.json
    email = data.get('email')
    role = data.get('role', 'contributor')
    
    if not email:
        return jsonify({"error": "Email required"}), 400
    
    # Check if user exists, if not create new user
    user = User.query.filter_by(email=email).first()
    if not user:
        # Create new user with the email
        user = User(email=email, name=email.split('@')[0])
        db.session.add(user)
        db.session.commit()
    
    # Check if user is already in workspace
    existing = WorkspaceMember.query.filter_by(
        workspace_id=ws_id, user_id=user.id
    ).first()
    if existing:
        return jsonify({"error": "User already in workspace"}), 400
    
    # Add user to workspace
    member = WorkspaceMember(
        workspace_id=ws_id,
        user_id=user.id,
        role_id=role
    )
    db.session.add(member)
    db.session.commit()
    
    return jsonify({"status": "invited", "userId": user.id}), 201

@workspace_bp.route('/workspaces/<ws_id>/members/<member_id>', methods=['DELETE'])
@jwt_required()
def remove_workspace_member(ws_id, member_id):
    """Remove a member from workspace (only owner can remove)"""
    current_user = get_jwt_identity()
    workspace = Workspace.query.get(ws_id)
    
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only workspace owner can remove members"}), 403
    
    member = WorkspaceMember.query.get(member_id)
    if not member or member.workspace_id != ws_id:
        return jsonify({"error": "Member not found"}), 404
    
    db.session.delete(member)
    db.session.commit()
    
    return jsonify({"status": "removed"}), 200

# --- PROJECT MEMBER MANAGEMENT ---

@workspace_bp.route('/projects/<project_id>/members', methods=['GET'])
@jwt_required()
def get_project_members(project_id):
    """Get all members assigned to a project"""
    members = ProjectMember.query.filter_by(project_id=project_id).all()
    result = []
    for m in members:
        user = User.query.get(m.user_id)
        if user:
            result.append({
                "id": m.id,
                "userId": m.user_id,
                "name": user.name,
                "email": user.email,
                "avatar": user.avatar,
                "role": m.role,
                "assignedAt": m.assigned_at.isoformat() if m.assigned_at else None
            })
    return jsonify(result)

@workspace_bp.route('/projects/<project_id>/assign-member', methods=['POST'])
@jwt_required()
def assign_project_member(project_id):
    """Assign a user to a project (only workspace owner can assign)"""
    current_user = get_jwt_identity()
    project = Project.query.get(project_id)
    
    if not project:
        return jsonify({"error": "Project not found"}), 404
    
    # Check if current user is workspace owner
    workspace = Workspace.query.get(project.workspace_id)
    if not workspace or workspace.owner_id != current_user:
        return jsonify({"error": "Only workspace owner can assign members"}), 403
    
    data = request.json
    user_id = data.get('userId')
    role = data.get('role', 'contributor')
    
    if not user_id:
        return jsonify({"error": "userId required"}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Check if user is already in project
    existing = ProjectMember.query.filter_by(
        project_id=project_id, user_id=user_id
    ).first()
    if existing:
        return jsonify({"error": "User already assigned to project"}), 400
    
    # Assign user to project
    member = ProjectMember(
        project_id=project_id,
        user_id=user_id,
        role=role
    )
    db.session.add(member)
    db.session.commit()
    
    return jsonify({"status": "assigned", "projectMemberId": member.id}), 201

@workspace_bp.route('/projects/<project_id>/members/<member_id>', methods=['DELETE'])
@jwt_required()
def unassign_project_member(project_id, member_id):
    """Unassign a user from a project (only owner can unassign)"""
    current_user = get_jwt_identity()
    project = Project.query.get(project_id)
    
    if not project:
        return jsonify({"error": "Project not found"}), 404
    
    workspace = Workspace.query.get(project.workspace_id)
    if not workspace or workspace.owner_id != current_user:
        return jsonify({"error": "Only workspace owner can unassign members"}), 403
    
    member = ProjectMember.query.get(member_id)
    if not member or member.project_id != project_id:
        return jsonify({"error": "Member not found"}), 404
    
    db.session.delete(member)
    db.session.commit()
    
    return jsonify({"status": "unassigned"}), 200

# --- GENERIC DATA OPS ---

@workspace_bp.route('/workspaces/<ws_id>', methods=['PATCH'])
@jwt_required()
def update_workspace(ws_id):
    current_user = get_jwt_identity()
    workspace = Workspace.query.get(ws_id)
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
    if workspace.owner_id != current_user:
        return jsonify({"error": "Only workspace owner can update settings"}), 403
    data = request.json
    if data.get('name'): workspace.name = data['name']
    if data.get('companyWebsite') is not None: workspace.company_website = data['companyWebsite']
    if data.get('location') is not None: workspace.location = data['location']
    if data.get('employeeCount') is not None: workspace.employee_count = data['employeeCount']
    if data.get('aiContextDescription') is not None: workspace.ai_context_description = data['aiContextDescription']
    db.session.commit()
    return jsonify({"status": "updated"})

@workspace_bp.route('/companies', methods=['POST'])
@jwt_required()
def add_company():
    data = request.json
    # Clean data to match DB model
    data.pop('projects', None) 
    
    # Map camelCase to snake_case if needed
    if 'workspaceId' in data:
        data['workspace_id'] = data.pop('workspaceId')

    c = Company(**data)
    db.session.add(c)
    db.session.commit()
    return jsonify({"status": "ok"})

@workspace_bp.route('/companies/<c_id>/projects', methods=['POST'])
@jwt_required()
def add_project(c_id):
    data = request.json
    data['company_id'] = c_id
    
    # Map fields and remove relationships
    data.pop('tasks', None)
    
    workspace_id = data.get('workspaceId')
    
    p = Project(
        id=data['id'], 
        workspace_id=workspace_id,
        company_id=c_id,
        name=data['name'],
        type=data['type'],
        mission=data.get('mission'),
        progress=0,
        whiteboard=data.get('whiteboard', [])
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({"status": "ok"})

@workspace_bp.route('/projects/<p_id>/tasks', methods=['POST'])
@jwt_required()
def add_tasks(p_id):
    tasks_data = request.json['tasks']
    for t_data in tasks_data:
        due_raw = t_data.get('dueDate')
        due_date = datetime.fromisoformat(due_raw) if due_raw else None
        t = Task(
            id=t_data['id'],
            workspace_id=t_data['workspaceId'],
            project_id=p_id,
            title=t_data['title'],
            description=t_data.get('description'),
            status=t_data['status'],
            priority=t_data['priority'],
            estimated_hours=t_data.get('estimatedHours'),
            due_date=due_date,
            labels=t_data.get('labels', []),
            assignee_id=t_data.get('assigneeId'),
            issue_type=t_data.get('issueType', 'task')
        )
        db.session.add(t)
    db.session.commit()
    return jsonify({"status": "ok"})

# --- NOTES MANAGEMENT (Design Thinking Enhanced) ---

@workspace_bp.route('/workspaces/<ws_id>/notes', methods=['GET'])
@jwt_required()
def get_notes(ws_id):
    """
    Get notes for a workspace with privacy filtering.
    - Owners see everything.
    - Members see 'public'/'team' notes + their own 'private' notes.
    """
    current_user_id = get_jwt_identity()
    workspace = Workspace.query.get(ws_id)
    
    if not workspace:
        return jsonify({"error": "Workspace not found"}), 404
        
    # Check query params for context filtering (e.g., specific project)
    context_id = request.args.get('contextId')
    
    query = Note.query.filter_by(workspace_id=ws_id)
    
    if context_id:
        query = query.filter_by(context_id=context_id)
        
    all_notes = query.all()
    visible_notes = []
    
    for note in all_notes:
        # Rule 1: Owner of the note sees it
        if note.owner_id == current_user_id:
            visible_notes.append(note)
            continue
            
        # Rule 2: Workspace Admin/Owner sees everything (optional, but good for oversight)
        if workspace.owner_id == current_user_id:
            visible_notes.append(note)
            continue
            
        # Rule 3: Public/Team notes are visible to workspace members
        # (Assuming caller is a member if they passed auth & basic checks, 
        #  but ideally we verify membership first)
        if note.visibility in ['public', 'team']:
            visible_notes.append(note)
            
    return jsonify([{
        "id": n.id,
        "content": n.content,
        "type": n.type,
        "color": n.color,
        "ownerId": n.owner_id,
        "visibility": n.visibility,
        "createdAt": n.created_at.isoformat()
    } for n in visible_notes])

@workspace_bp.route('/workspaces/<ws_id>/notes', methods=['POST'])
@jwt_required()
def create_note(ws_id):
    current_user_id = get_jwt_identity()
    data = request.json
    
    note = Note(
        workspace_id=ws_id,
        context_id=data.get('contextId'), # Project ID or null
        owner_id=current_user_id,
        visibility=data.get('visibility', 'private'),
        content=data.get('content', ''),
        type=data.get('type', 'general'),
        color=data.get('color', 'yellow')
    )
    
    db.session.add(note)
    db.session.commit()
    
    return jsonify({"status": "created", "id": note.id, "visibility": note.visibility}), 201

@workspace_bp.route('/notes/<note_id>', methods=['DELETE'])
@jwt_required()
def delete_note(note_id):
    current_user_id = get_jwt_identity()
    note = Note.query.get(note_id)
    
    if not note:
        return jsonify({"error": "Note not found"}), 404
        
    if note.owner_id != current_user_id:
        return jsonify({"error": "Unauthorized"}), 403
        
    db.session.delete(note)
    db.session.commit()
    
    return jsonify({"status": "deleted"}), 200

# --- AI AGENT ROUTES ---

@agent_bp.route('/generate-plan', methods=['POST'])
@jwt_required()
def generate_plan():
    data = request.json
    service = AIService()
    tasks = service.generate_project_plan(
        data['project'], 
        data['companyMission'], 
        data['userGuidance'],
        data['persona']
    )
    return jsonify({"tasks": tasks})

@agent_bp.route('/executive-summary', methods=['POST'])
@jwt_required()
def exec_summary():
    data = request.json
    service = AIService()
    result = service.generate_summary(data['companies'], data['persona'])
    return jsonify(result)

@agent_bp.route('/scheduler-advice', methods=['POST'])
@jwt_required()
def scheduler_advice():
    data = request.json
    service = AIService()
    advice = service.generate_schedule(data['companies'], data['persona'])
    return jsonify({"advice": advice})

@agent_bp.route('/voice', methods=['POST'])
@jwt_required()
def voice_session():
    """
    Voice endpoint using Gemini Live API (google-genai >= 1.0).
    Frontend sends audio chunks as base64, receives audio responses.
    """
    try:
        import asyncio
        from google import genai
        from google.genai import types as gtypes

        user_id = get_jwt_identity()
        data = request.json

        persona = data.get('persona', 'general')
        audio_data = data.get('audio', '')

        if not audio_data:
            return jsonify({"error": "Audio data required"}), 400

        api_key = current_app.config.get('API_KEY')
        if not api_key:
            return jsonify({"error": "Gemini API key not configured"}), 500

        client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

        live_config = gtypes.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=gtypes.SpeechConfig(
                voice_config=gtypes.VoiceConfig(
                    prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(voice_name="Kore")
                )
            ),
            system_instruction=gtypes.Content(
                parts=[gtypes.Part(text=(
                    f"You are Sindhai, an intelligent Executive Chief of Staff for a {persona}. "
                    "Be concise, extremely sharp, and action-oriented."
                ))]
            )
        )

        response_audio = None

        async def _run_live():
            nonlocal response_audio
            async with client.aio.live.connect(
                model="gemini-2.0-flash-live-001",
                config=live_config
            ) as session:
                await session.send_realtime_input(
                    audio=gtypes.Blob(data=base64.b64decode(audio_data), mime_type="audio/pcm;rate=16000")
                )
                async for msg in session.receive():
                    if (msg.server_content and msg.server_content.model_turn
                            and msg.server_content.model_turn.parts):
                        for part in msg.server_content.model_turn.parts:
                            if part.inline_data:
                                response_audio = base64.b64encode(
                                    part.inline_data.data
                                ).decode("utf-8")
                                return  # got first audio chunk; exit

        asyncio.run(_run_live())
        
        return jsonify({
            "audio": response_audio,
            "status": "success"
        })
    
    except Exception as e:
        current_app.logger.error(f"Voice session error: {e}")
        return jsonify({"error": str(e)}), 500


# --- NOTES & DOCUMENTS ROUTES ---
# note: Create/Get notes logic moved to Workspace-scoped routes earlier in file.

@workspace_bp.route('/documents', methods=['POST'])
@jwt_required()
def upload_document():
    """Create document metadata after file upload to storage"""
    data = request.json
    doc = Document(
        id=data['id'],
        workspace_id=data['workspaceId'],
        name=data['name'],
        size=data['size'],
        type=data['type'],
        bucket_path=data['bucketPath'],
        tags=data.get('tags', [])
    )
    db.session.add(doc)
    db.session.commit()
    return jsonify({"status": "uploaded"})

@workspace_bp.route('/workspaces/<ws_id>/documents', methods=['GET'])
@jwt_required()
def get_documents(ws_id):
    """Fetch all documents in a workspace"""
    docs = Document.query.filter_by(workspace_id=ws_id).order_by(Document.uploaded_at.desc()).all()
    return jsonify([{
        'id': d.id,
        'name': d.name,
        'size': d.size,
        'type': d.type,
        'uploadedAt': d.uploaded_at.isoformat(),
        'bucketPath': d.bucket_path,
        'tags': d.tags
    } for d in docs])

@workspace_bp.route('/documents/<doc_id>', methods=['DELETE'])
@jwt_required()
def delete_document(doc_id):
    """Delete a document"""
    doc = Document.query.get(doc_id)
    if not doc:
        return jsonify({"error": "Document not found"}), 404
    
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"status": "deleted"})


# --- ANALYTICS ROUTES ---

@workspace_bp.route('/analytics/event', methods=['POST'])
def log_event():
    """Log an analytics event (fire-and-forget, no auth required for analytics)"""
    try:
        data = request.json
        log = ActivityLog(
            id=data.get('id'),
            event_name=data.get('eventName'),
            properties=data.get('properties', {}),
            timestamp=datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat()))
        )
        db.session.add(log)
        db.session.commit()
        return jsonify({"status": "logged"}), 200
    except Exception as e:
        # Fail silently for analytics
        current_app.logger.warning(f"Analytics logging failed: {e}")
        return jsonify({"status": "failed"}), 500

# --- CALENDAR ROUTES ---

@workspace_bp.route('/workspaces/<ws_id>/events', methods=['GET'])
@jwt_required()
def get_events(ws_id):
    """
    Get events for calendar. 
    Filters by start/end date (ISO format).
    """
    current_user_id = get_jwt_identity()
    start_str = request.args.get('start')
    end_str = request.args.get('end')
    
    query = CalendarEvent.query.filter_by(workspace_id=ws_id)
    
    if start_str:
        query = query.filter(CalendarEvent.start_time >= datetime.fromisoformat(start_str.replace('Z', '+00:00')))
    if end_str:
        query = query.filter(CalendarEvent.end_time <= datetime.fromisoformat(end_str.replace('Z', '+00:00')))
        
    all_events = query.all()
    visible_events = []
    
    workspace = Workspace.query.get(ws_id)
    
    for event in all_events:
        # Visibility rules
        if event.scope == 'personal' and event.owner_id != current_user_id:
            continue
        # Allow viewing workspace/company events
        visible_events.append(event)
        
    return jsonify([{
        "id": e.id,
        "title": e.title,
        "start": e.start_time.isoformat(),
        "end": e.end_time.isoformat(),
        "type": e.type,
        "scope": e.scope,
        "color": e.color,
        "taskId": e.task_id,
        "isAutoGenerated": e.is_auto_generated
    } for e in visible_events])

@workspace_bp.route('/workspaces/<ws_id>/events', methods=['POST'])
@jwt_required()
def create_event(ws_id):
    current_user_id = get_jwt_identity()
    data = request.json
    
    event = CalendarEvent(
        workspace_id=ws_id,
        owner_id=current_user_id,
        title=data.get('title'),
        start_time=datetime.fromisoformat(data.get('start')), # Expect ISO string
        end_time=datetime.fromisoformat(data.get('end')),
        type=data.get('type', 'block'),
        scope=data.get('scope', 'personal'),
        task_id=data.get('taskId'),
        color=data.get('color', 'blue')
    )
    
    db.session.add(event)
    db.session.commit()
    return jsonify({"status": "created", "id": event.id}), 201

@workspace_bp.route('/events/<event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    event = CalendarEvent.query.get(event_id)
    current_user_id = get_jwt_identity()
    
    if not event:
        return jsonify({"error": "Event not found"}), 404
        
    if event.owner_id != current_user_id: # And not admin... simplify for now
         return jsonify({"error": "Unauthorized"}), 403
         
    db.session.delete(event)
    db.session.commit()
    return jsonify({"status": "deleted"})
    
@agent_bp.route('/optimize-schedule', methods=['POST'])
@jwt_required()
def optimize_schedule():
    """
    AI Endpoint to arrange tasks into calendar slots.
    Input: { tasks: [], date: 'YYYY-MM-DD', workHours: {start: 9, end: 17} }
    Output: Dictionary of suggested events
    """
    data = request.json
    tasks = data.get('tasks', [])
    date_str = data.get('date') # Target date
    
    service = AIService()
    suggested_slots = service.optimize_daily_schedule(tasks, date_str)
    
    # Post-process: Add full timestamps based on start/end times
    # Assuming output is [{ "start": "09:00", "end": "10:30", ... }]
    
    final_events = []
    base_date = datetime.fromisoformat(date_str) if date_str else datetime.now()
    
    for slot in suggested_slots:
        try:
            start_parts = slot['start'].split(':')
            end_parts = slot['end'].split(':')
            
            start_dt = base_date.replace(hour=int(start_parts[0]), minute=int(start_parts[1]), second=0)
            end_dt = base_date.replace(hour=int(end_parts[0]), minute=int(end_parts[1]), second=0)
            
            final_events.append({
                "title": slot['title'],
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "type": slot['type'],
                "taskId": slot.get('taskId'),
                "scope": 'personal',
                "isAutoGenerated": True
            })
        except Exception as e:
            current_app.logger.error(f"Slot parsing error: {e}")
            continue
            
    return jsonify(final_events)
        
    return jsonify(suggested_events)




