import uuid
from datetime import datetime
from .extensions import db
from sqlalchemy.dialects.postgresql import JSONB

def generate_uuid():
    return str(uuid.uuid4())

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    email = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String)
    avatar = db.Column(db.String)
    
    # Profile Fields
    gender = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)
    age = db.Column(db.Integer, nullable=True)
    location = db.Column(db.String, nullable=True)
    country = db.Column(db.String, nullable=True)
    purpose = db.Column(db.String, nullable=True)  # learning|freelancing|personal|startup|enterprise
    is_onboarded = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # OTP Storage (For demo/MVP purposes, storing mostly in memory or temp table preferred in high scale)
    otp_code = db.Column(db.String, nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)

class Organization(db.Model):
    """
    Represents a Company or Institution.
    Allows for the 'Company' context in the application.
    """
    __tablename__ = 'organizations'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    name = db.Column(db.String, nullable=False)
    domain = db.Column(db.String, unique=True, nullable=True) # e.g., 'mit.edu'
    owner_id = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Enterprise Settings
    subscription_plan = db.Column(db.String, default='free') # free, pro, enterprise
    settings = db.Column(JSONB, default={}) # White-labeling, SSO config, etc.

class OrganizationMember(db.Model):
    __tablename__ = 'organization_members'
    organization_id = db.Column(db.String, db.ForeignKey('organizations.id'), primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), primary_key=True)
    role = db.Column(db.String, default='member') # owner, admin, member
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String, default='active') # active, invited, suspended

class Workspace(db.Model):
    __tablename__ = 'workspaces'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    name = db.Column(db.String)
    
    # Core Separation: Personal vs Company
    # context: 'personal' | 'company'
    context = db.Column(db.String, nullable=False, default='personal') 
    
    # Core Function: Study vs Project
    # type: 'study' | 'project'
    type = db.Column(db.String, nullable=False, default='project')
    
    # Relations
    owner_id = db.Column(db.String, db.ForeignKey('users.id')) # If personal
    organization_id = db.Column(db.String, db.ForeignKey('organizations.id'), nullable=True) # If company
    
    description = db.Column(db.String)
    persona = db.Column(db.String) # Keep for backward compatibility/AI Context
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    settings = db.Column(JSONB, default={})
    
    # Enterprise Fields (Legacy support, prefer moving to JSONB or Organization)
    company_website = db.Column(db.String)
    location = db.Column(db.String)
    employee_count = db.Column(db.String)
    category = db.Column(db.String)
    ai_context_description = db.Column(db.String)

class WorkspaceMember(db.Model):
    __tablename__ = 'workspace_members'
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), primary_key=True)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.String)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class ProjectMember(db.Model):
    __tablename__ = 'project_members'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String, db.ForeignKey('projects.id'))
    user_id = db.Column(db.String, db.ForeignKey('users.id'))
    role = db.Column(db.String, default='contributor')  # owner, contributor, viewer
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)

class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    name = db.Column(db.String)
    mission = db.Column(db.Text)
    color = db.Column(db.String)
    whiteboard = db.Column(JSONB, default=list)

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    company_id = db.Column(db.String, db.ForeignKey('companies.id'))
    name = db.Column(db.String)
    type = db.Column(db.String)
    mission = db.Column(db.Text)
    progress = db.Column(db.Integer, default=0)
    whiteboard = db.Column(JSONB, default=list)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    project_id = db.Column(db.String, db.ForeignKey('projects.id'))
    title = db.Column(db.String)
    description = db.Column(db.Text)
    status = db.Column(db.String)
    priority = db.Column(db.String)
    estimated_hours = db.Column(db.Float)
    is_daily_focus = db.Column(db.Boolean, default=False)
    resources = db.Column(JSONB, default=list)
    # Jira-style fields
    due_date = db.Column(db.DateTime, nullable=True)
    labels = db.Column(JSONB, default=list)          # ['bug', 'frontend', ...]
    assignee_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    issue_type = db.Column(db.String, default='task')  # task|bug|feature|story

class Note(db.Model):
    __tablename__ = 'notes'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    context_id = db.Column(db.String) # Could be Project ID or just generic
    
    owner_id = db.Column(db.String, db.ForeignKey('users.id')) # Creator
    visibility = db.Column(db.String, default='private') # 'private' | 'public' | 'team'
    
    content = db.Column(db.Text)
    type = db.Column(db.String, default='general')
    color = db.Column(db.String)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CalendarEvent(db.Model):
    __tablename__ = 'calendar_events'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    owner_id = db.Column(db.String, db.ForeignKey('users.id')) # Creator/Owner
    title = db.Column(db.String)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    type = db.Column(db.String) # 'task_block', 'meeting', 'personal', 'reminder'
    scope = db.Column(db.String, default='personal') # 'personal', 'workspace', 'company'
    task_id = db.Column(db.String, db.ForeignKey('tasks.id'), nullable=True) # Linked task
    color = db.Column(db.String, default='blue')
    is_auto_generated = db.Column(db.Boolean, default=False)

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    event_name = db.Column(db.String)
    properties = db.Column(JSONB)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    # Data warehouse dimensions
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'), nullable=True)
    session_id = db.Column(db.String, nullable=True)  # browser session
    platform = db.Column(db.String, nullable=True)    # web|mobile|api

class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.String, primary_key=True, default=generate_uuid)
    workspace_id = db.Column(db.String, db.ForeignKey('workspaces.id'))
    name = db.Column(db.String)
    size = db.Column(db.Integer)
    type = db.Column(db.String) # mimetype
    bucket_path = db.Column(db.String)
    tags = db.Column(JSONB, default=list)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
