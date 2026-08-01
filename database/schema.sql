-- Users Table
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    name VARCHAR,
    avatar VARCHAR,
    gender VARCHAR,
    phone VARCHAR,
    age INTEGER,
    location VARCHAR,
    is_onboarded BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    otp_code VARCHAR,
    otp_expiry TIMESTAMP
);

-- Organizations Table (New Enterprise Layer)
CREATE TABLE organizations (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    domain VARCHAR UNIQUE,
    owner_id VARCHAR REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    subscription_plan VARCHAR DEFAULT 'free',
    settings JSONB DEFAULT '{}'
);

-- Organization Members (RBAC for Admin Console)
CREATE TABLE organization_members (
    organization_id VARCHAR REFERENCES organizations(id),
    user_id VARCHAR REFERENCES users(id),
    role VARCHAR DEFAULT 'member', -- 'owner', 'admin', 'member'
    status VARCHAR DEFAULT 'active', -- 'active', 'invited', 'suspended'
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (organization_id, user_id)
);

-- Workspaces Table (Updated for Dual Context)
CREATE TABLE workspaces (
    id VARCHAR PRIMARY KEY,
    name VARCHAR,
    context VARCHAR DEFAULT 'personal', -- 'personal' or 'company'
    type VARCHAR DEFAULT 'project', -- 'study' or 'project'
    owner_id VARCHAR REFERENCES users(id), -- Nullable if company
    organization_id VARCHAR REFERENCES organizations(id), -- Nullable if personal
    description VARCHAR,
    persona VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}',
    -- Legacy Enterprise Fields (Can be deprecated later)
    company_website VARCHAR,
    location VARCHAR,
    employee_count VARCHAR,
    category VARCHAR,
    ai_context_description VARCHAR
);

-- Workspace Members (Many-to-Many)
CREATE TABLE workspace_members (
    workspace_id VARCHAR REFERENCES workspaces(id),
    user_id VARCHAR REFERENCES users(id),
    role_id VARCHAR, -- 'admin', 'member', 'viewer'
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (workspace_id, user_id)
);

-- Companies (Legacy concept, now effectively 'Departments' or 'Teams' inside a Workspace)
-- In V2, we might migrate this to just 'Projects' with tags, but keeping for compatibility
CREATE TABLE companies (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR REFERENCES workspaces(id),
    name VARCHAR,
    mission TEXT,
    color VARCHAR,
    whiteboard JSONB DEFAULT '[]'
);

-- Projects
CREATE TABLE projects (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR REFERENCES workspaces(id),
    company_id VARCHAR REFERENCES companies(id), -- Optional now?
    name VARCHAR,
    type VARCHAR, -- 'build', 'learning', 'research'
    mission TEXT,
    progress INTEGER DEFAULT 0,
    whiteboard JSONB DEFAULT '[]'
);

-- Project Members (Granular Access)
CREATE TABLE project_members (
    id VARCHAR PRIMARY KEY,
    project_id VARCHAR REFERENCES projects(id),
    user_id VARCHAR REFERENCES users(id),
    role VARCHAR DEFAULT 'contributor',
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
CREATE TABLE tasks (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR REFERENCES workspaces(id),
    project_id VARCHAR REFERENCES projects(id),
    title VARCHAR,
    description TEXT,
    status VARCHAR,
    priority VARCHAR,
    estimated_hours FLOAT,
    is_daily_focus BOOLEAN DEFAULT FALSE,
    resources JSONB DEFAULT '[]'
);

-- Notes (Enhanced for Privacy)
CREATE TABLE notes (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR REFERENCES workspaces(id),
    context_id VARCHAR, -- Can link to Project ID
    owner_id VARCHAR REFERENCES users(id),
    visibility VARCHAR DEFAULT 'private', -- 'private', 'team', 'public'
    content TEXT,
    type VARCHAR DEFAULT 'general',
    color VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Activity Logs
CREATE TABLE activity_logs (
    id VARCHAR PRIMARY KEY,
    event_name VARCHAR,
    properties JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
