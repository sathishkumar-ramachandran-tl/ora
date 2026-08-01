-- =============================================================
-- Sindhai Cortex v2 - Agentic AI Schema Migration
-- Run AFTER the base schema.sql
-- =============================================================

-- Chat Sessions (one per conversation thread)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    workspace_id VARCHAR REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id VARCHAR REFERENCES users(id),
    title VARCHAR DEFAULT 'New Conversation',
    -- Snapshot of context at session creation for agent grounding
    context JSONB DEFAULT '{}',
    -- LangGraph thread_id mapped here (same as id for simplicity)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace ON chat_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);

-- Chat Messages (full conversation history per session)
CREATE TABLE IF NOT EXISTS chat_messages (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    session_id VARCHAR REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content TEXT,
    -- Stores tool calls, agent_type, artifacts (task lists etc.) as JSONB
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

-- Agent Tool Calls (audit/traceability log)
CREATE TABLE IF NOT EXISTS agent_tool_calls (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    session_id VARCHAR REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id VARCHAR REFERENCES chat_messages(id),
    tool_name VARCHAR NOT NULL,
    tool_input JSONB DEFAULT '{}',
    tool_output JSONB DEFAULT '{}',
    status VARCHAR DEFAULT 'success' CHECK (status IN ('success', 'error', 'pending')),
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_session ON agent_tool_calls(session_id);

-- Planning Sessions (multi-turn planning state)
CREATE TABLE IF NOT EXISTS planning_sessions (
    id VARCHAR PRIMARY KEY DEFAULT gen_random_uuid()::varchar,
    chat_session_id VARCHAR REFERENCES chat_sessions(id) ON DELETE CASCADE,
    workspace_id VARCHAR REFERENCES workspaces(id),
    project_id VARCHAR REFERENCES projects(id),   -- target project if planning for one
    phase VARCHAR DEFAULT 'gathering'
        CHECK (phase IN ('gathering', 'drafting', 'refining', 'confirming', 'executed')),
    -- The draft plan as it evolves through the conversation
    draft_plan JSONB DEFAULT '{}',
    -- Clarification questions asked and answered
    qa_pairs JSONB DEFAULT '[]',
    -- User-provided corrections
    corrections JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_planning_sessions_updated_at
    BEFORE UPDATE ON planning_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Also add updated_at to tasks for better tracking
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS assigned_to VARCHAR REFERENCES users(id);
ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date TIMESTAMP;

-- Add updated_at to projects
ALTER TABLE projects ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE projects ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
