# Sindhai Cortex v2 — Complete Architecture Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [Agentic AI Architecture](#2-agentic-ai-architecture)
3. [Database Design](#3-database-design)
4. [Backend API Reference](#4-backend-api-reference)
5. [Frontend Architecture](#5-frontend-architecture)
6. [MCP Server](#6-mcp-server)
7. [A2A Protocol](#7-a2a-agent-to-agent-protocol)
8. [Mobile-First Design](#8-mobile-first-design)
9. [Multi-Discussion Planning](#9-multi-discussion-planning)
10. [Deployment Guide](#10-deployment-guide)

---

## 1. System Overview

Sindhai Cortex is an AI-native operating system for freelancers and students to manage projects, learning, and execution. v2 adds a **multi-agent conversational AI** layer on top of the existing workspace management system.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CLIENT LAYER (React + Vite)               │
│  ┌─────────────────┐  ┌───────────────┐  ┌───────────────┐  │
│  │  PersonalLayout │  │ CompanyLayout │  │ ChatInterface │  │
│  │  (mobile-first) │  │ (mobile-first)│  │  (floating)   │  │
│  └─────────────────┘  └───────────────┘  └───────────────┘  │
│           │                    │                  │           │
│           └────────────────────┴──────────────────┘          │
│                          ▼ SSE / REST                         │
└─────────────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────────────┐
│                   API LAYER (Flask + Blueprints)              │
│  ┌───────────┐ ┌──────────┐ ┌─────────┐ ┌───────────────┐  │
│  │ /api/v1/* │ │/api/v2/* │ │/chat/*  │ │ /.well-known/ │  │
│  │ (core)    │ │(enterprise│ │(agentic)│ │   (A2A card)  │  │
│  └───────────┘ └──────────┘ └─────────┘ └───────────────┘  │
│                              │                                │
└──────────────────────────────┼──────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 MULTI-AGENT LAYER (LangGraph)                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              ORCHESTRATOR (router_node)              │    │
│  │             Gemini 2.0 Flash — intent routing        │    │
│  └──────┬──────────┬──────────┬─────────────┬──────────┘    │
│         │          │          │             │                │
│  ┌──────▼─┐ ┌──────▼─┐ ┌────▼────┐ ┌──────▼──────┐        │
│  │ QUERY  │ │  CRUD  │ │PLANNING │ │  ANALYSIS   │        │
│  │ AGENT  │ │ AGENT  │ │  AGENT  │ │   AGENT     │        │
│  │ Pro    │ │ Flash  │ │  Pro    │ │   Pro       │        │
│  └────────┘ └────────┘ └─────────┘ └─────────────┘        │
│         │          │          │             │                │
│         └──────────┴──────────┴─────────────┘                │
│                              │                                │
│                    SQLAlchemy / PostgreSQL                     │
└─────────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAYER (PostgreSQL)                     │
│  users · workspaces · projects · tasks · notes · events      │
│  chat_sessions · chat_messages · agent_tool_calls            │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + TypeScript + Vite | SPA application |
| Styling | TailwindCSS + Lucide React | Mobile-first UI |
| State | React Context + Custom Hooks | Auth + Chat state |
| HTTP | Axios (REST) + fetch (SSE) | API communication |
| Backend | Flask 3.0 + Blueprints | REST API |
| ORM | SQLAlchemy + Flask-SQLAlchemy | Database access |
| Auth | JWT (Flask-JWT-Extended) | Session tokens |
| Agentic AI | LangGraph 0.2+ | Multi-agent orchestration |
| LLM Integration | LangChain + Google GenAI | Model calls + tools |
| AI Models | Gemini 2.0 Flash / 2.5 Pro | Orchestration + reasoning |
| MCP | mcp 1.0+ | External tool exposure |
| A2A | Custom REST + JSON-LD | Agent discovery |
| Database | PostgreSQL (Neon) | Persistent storage |
| Email | Gmail API (OAuth2) | OTP delivery |
| Deployment | GCP Cloud Run + Docker | Container hosting |

---

## 2. Agentic AI Architecture

### 2.1 Agent Graph (LangGraph StateGraph)

File: `backend/app/agents/orchestrator.py`

```
User Message
     │
     ▼
router_node (Gemini 2.0 Flash)
 • Classifies intent: crud | query | plan | analyze
 • Checks if planning session already active → routes to planning
     │
     ├──── query ────► query_agent (ReAct, Gemini 2.5 Pro)
     │                  Tools: get_workspace_summary, get_tasks,
     │                         analyze_workspace_progress, get_projects
     │
     ├──── crud  ────► crud_agent (ReAct, Gemini 2.0 Flash)
     │                  Tools: create_task, create_multiple_tasks,
     │                         update_task, update_task_status,
     │                         create_project, create_initiative,
     │                         delete_task, delete_project, create_note
     │
     ├──── plan  ────► planning_agent (ReAct, Gemini 2.5 Pro)
     │                  Tools: get_workspace_summary, get_projects,
     │                         create_multiple_tasks, create_project
     │                  State: planning_phase persisted via checkpoints
     │
     └── analyze ────► analysis_agent (ReAct, Gemini 2.5 Pro)
                        Tools: get_workspace_summary, get_tasks,
                               analyze_workspace_progress, get_projects
```

### 2.2 Agent State

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # Full conversation history
    workspace_id: str                         # Current workspace scope
    user_id: str                              # Authenticated user
    intent: Optional[str]                     # Classified intent
    active_agent: Optional[str]              # Which agent is active
    workspace_context: Optional[dict]         # Snapshot for grounding
    planning_phase: Optional[str]            # multi-turn planning phase
    draft_plan: Optional[dict]               # Evolving plan draft
    planning_project_id: Optional[str]       # Target project for planning
```

### 2.3 Multi-Model Strategy

| Agent | Model | Why |
|-------|-------|-----|
| Router | `gemini-2.0-flash-exp` | Fast, cheap intent classification |
| Query Agent | `gemini-2.5-pro-exp` | Complex data reasoning |
| CRUD Agent | `gemini-2.0-flash-exp` | Fast, reliable mutations |
| Planning Agent | `gemini-2.5-pro-exp` | Deep multi-turn reasoning |
| Analysis Agent | `gemini-2.5-pro-exp` | Strategic insight generation |

### 2.4 Tool System

All tools are LangChain `@tool` decorated functions in `backend/app/agents/tools.py`.
They access the database directly via SQLAlchemy (no HTTP round-trip) since they run in Flask application context.

**Read Tools (Query + Analysis agents):**
- `get_workspace_summary(workspace_id)` → full hierarchy snapshot
- `get_tasks(workspace_id, project_id?, status?, priority?)` → filtered task list
- `analyze_workspace_progress(workspace_id)` → metrics, bottlenecks, suggestions
- `get_projects(workspace_id)` → project list with initiative context

**CRUD Tools (CRUD agent):**
- `create_task(project_id, workspace_id, title, ...)` → new task
- `create_multiple_tasks(project_id, workspace_id, tasks_json)` → batch create
- `create_project(initiative_id, workspace_id, name, ...)` → new project
- `create_initiative(workspace_id, name, ...)` → new initiative
- `update_task(task_id, ...fields)` → partial update
- `update_task_status(task_id, new_status)` → move on board
- `update_project(project_id, ...fields)` → project update
- `delete_task(task_id)` → permanent delete
- `delete_project(project_id)` → cascade delete with tasks
- `create_note(workspace_id, content, project_id?)` → note creation

### 2.5 Checkpointing (Multi-turn Memory)

LangGraph's `MemorySaver` stores agent state keyed by `thread_id = session_id`.
Each HTTP request to the chat API restores state from the checkpoint, enabling:
- Persistent conversation history within a session
- Planning phase progression across multiple turns
- Draft plan updates without re-starting the conversation

For production scale, replace `MemorySaver` with `PostgresSaver`:
```python
from langgraph.checkpoint.postgres import PostgresSaver
checkpointer = PostgresSaver.from_conn_string(DATABASE_URL)
```

### 2.6 SSE Streaming

The chat endpoint uses Flask's `stream_with_context` + `Response` with `text/event-stream` MIME type.

Event stream format:
```
data: {"type": "chunk", "content": "text...", "node": "query_agent"}\n\n
data: {"type": "tool_call", "name": "get_tasks", "status": "running"}\n\n
data: {"type": "tool_result", "name": "get_tasks", "result": [...]}\n\n
data: {"type": "done", "message_id": "uuid"}\n\n
data: {"type": "error", "message": "..."}\n\n
```

Frontend consumes via `fetch` + `ReadableStream` (NOT EventSource, since we need POST).

---

## 3. Database Design

### 3.1 Core Tables (v1)

```sql
users (id, email, name, avatar, gender, phone, age, location, is_onboarded, otp_code, otp_expiry)
organizations (id, name, domain, owner_id, subscription_plan, settings)
organization_members (organization_id, user_id, role, status, joined_at)
workspaces (id, name, context, type, owner_id, organization_id, persona, settings, ...)
workspace_members (workspace_id, user_id, role_id, joined_at)
companies (id, workspace_id, name, mission, color, whiteboard)
projects (id, workspace_id, company_id, name, type, mission, progress, whiteboard)
project_members (id, project_id, user_id, role, assigned_at)
tasks (id, workspace_id, project_id, title, description, status, priority, estimated_hours, is_daily_focus, resources)
notes (id, workspace_id, context_id, owner_id, visibility, content, type, color, created_at)
calendar_events (id, workspace_id, owner_id, title, start_time, end_time, type, scope, task_id, color, is_auto_generated)
documents (id, workspace_id, name, size, type, bucket_path, tags, uploaded_at)
activity_logs (id, event_name, properties, timestamp)
```

### 3.2 Agentic AI Tables (v2)

```sql
-- Conversation sessions
chat_sessions (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR REFERENCES workspaces(id),
    user_id VARCHAR REFERENCES users(id),
    title VARCHAR,
    context JSONB,          -- workspace snapshot at session start
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)

-- Individual messages
chat_messages (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR REFERENCES chat_sessions(id),
    role VARCHAR,           -- 'user' | 'assistant'
    content TEXT,
    metadata JSONB,         -- tool_calls, agent_type, artifacts
    created_at TIMESTAMP
)

-- Tool execution audit log
agent_tool_calls (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR,
    message_id VARCHAR,
    tool_name VARCHAR,
    tool_input JSONB,
    tool_output JSONB,
    status VARCHAR,         -- 'success' | 'error'
    duration_ms INTEGER,
    created_at TIMESTAMP
)

-- Multi-turn planning state
planning_sessions (
    id VARCHAR PRIMARY KEY,
    chat_session_id VARCHAR,
    workspace_id VARCHAR,
    project_id VARCHAR,
    phase VARCHAR,          -- 'gathering' | 'drafting' | 'refining' | 'confirming' | 'executed'
    draft_plan JSONB,
    qa_pairs JSONB,
    corrections JSONB,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### 3.3 Schema Relationships

```
users ──1:N──► workspaces (owner_id)
users ──M:N──► workspaces (via workspace_members)
workspaces ──1:N──► companies
companies ──1:N──► projects
projects ──1:N──► tasks
workspaces ──1:N──► chat_sessions
chat_sessions ──1:N──► chat_messages
chat_sessions ──1:N──► agent_tool_calls
```

### 3.4 Migration Instructions

```sql
-- Run base schema first
\i database/schema.sql

-- Then run v2 additions
\i database/v2_agentic_schema.sql
```

---

## 4. Backend API Reference

### 4.1 Authentication

All endpoints except `/health`, `/analytics/event`, `/a2a/*`, `/.well-known/*` require:
```
Authorization: Bearer <jwt_token>
```

**Get token:**
```
POST /api/v1/auth/request-otp   { "email": "user@example.com" }
POST /api/v1/auth/verify-otp    { "email": "...", "code": "123456" }
→ { "token": "eyJ...", "user": { id, email, name } }
```

### 4.2 Core API (v1)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/auth/me` | Current user profile |
| POST | `/api/v1/auth/request-otp` | Send OTP to email |
| POST | `/api/v1/auth/verify-otp` | Verify OTP, get JWT |
| POST | `/api/v1/workspaces` | Create workspace |
| GET | `/api/v1/users/{uid}/workspaces` | List user workspaces |
| GET | `/api/v1/workspaces/{id}/full-state` | Full hierarchy (companies→projects→tasks) |
| GET | `/api/v1/workspaces/{id}/members` | Workspace member list |
| POST | `/api/v1/workspaces/{id}/invite` | Invite member |
| DELETE | `/api/v1/workspaces/{id}/members/{mid}` | Remove member |
| POST | `/api/v1/companies` | Create initiative |
| POST | `/api/v1/companies/{id}/projects` | Create project |
| POST | `/api/v1/projects/{id}/tasks` | Create tasks (batch) |
| POST | `/api/v1/projects/{id}/assign-member` | Assign user to project |
| GET | `/api/v1/notes` | Get notes (filtered) |
| POST | `/api/v1/notes` | Create note |
| DELETE | `/api/v1/notes/{id}` | Delete note |
| GET | `/api/v1/workspaces/{id}/documents` | List documents |
| POST | `/api/v1/documents` | Upload document metadata |
| GET | `/api/v1/workspaces/{id}/events` | List calendar events |
| POST | `/api/v1/workspaces/{id}/events` | Create event |
| POST | `/api/v1/agents/generate-plan` | AI task generation (legacy) |
| POST | `/api/v1/agents/executive-summary` | AI executive summary |
| POST | `/api/v1/agents/scheduler-advice` | AI schedule strategy |
| POST | `/api/v1/agents/voice` | Gemini Live voice |

### 4.3 Enterprise API (v2)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v2/orgs` | Create organization |
| GET | `/api/v2/orgs` | List user's organizations |
| GET | `/api/v2/orgs/{id}/dashboard` | Org stats |
| GET | `/api/v2/orgs/{id}/members` | Org members |
| POST | `/api/v2/orgs/{id}/members` | Invite org member |
| PUT | `/api/v2/orgs/{id}/members/{uid}` | Update member role |
| POST | `/api/v2/workspaces` | Create workspace (v2) |
| GET | `/api/v2/workspaces` | List workspaces |

### 4.4 Agentic Chat API (v1/chat)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/chat/sessions` | Create chat session |
| GET | `/api/v1/chat/sessions` | List sessions (paginated) |
| GET | `/api/v1/chat/sessions/{id}` | Get session + messages |
| DELETE | `/api/v1/chat/sessions/{id}` | Delete session |
| **POST** | **`/api/v1/chat/sessions/{id}/messages`** | **Send message (SSE stream)** |

**Create Session:**
```json
POST /api/v1/chat/sessions
{ "workspace_id": "ws-uuid" }
→ { "id": "sess-uuid", "title": "New Conversation", "workspaceId": "...", "createdAt": "..." }
```

**Send Message (SSE stream):**
```json
POST /api/v1/chat/sessions/{id}/messages
{ "content": "List my high priority tasks", "workspace_id": "ws-uuid" }
→ text/event-stream:
  data: {"type":"chunk","content":"Let me check","node":"query_agent"}
  data: {"type":"tool_call","name":"get_tasks","status":"running"}
  data: {"type":"tool_result","name":"get_tasks","result":[...]}
  data: {"type":"chunk","content":"Here are your high priority tasks:","node":"query_agent"}
  data: {"type":"done","message_id":"msg-uuid"}
```

**Example chat interactions:**

| User says | Routed to | Tools used |
|-----------|-----------|------------|
| "Show me all pending tasks" | query_agent | `get_tasks` |
| "Create a task for writing blog post" | crud_agent | `get_projects`, `create_task` |
| "Analyze my workspace" | analysis_agent | `analyze_workspace_progress` |
| "Help me plan a new product launch" | planning_agent | `get_workspace_summary`, `create_multiple_tasks` |
| "Mark task X as done" | crud_agent | `update_task_status` |
| "Which projects are stalled?" | analysis_agent | `analyze_workspace_progress` |
| "Delete the research project" | crud_agent | `get_projects`, `delete_project` |

---

## 5. Frontend Architecture

### 5.1 Directory Structure

```
frontend/src/
├── api/
│   ├── client.ts          # Axios instances (v1, v2) + auth interceptors
│   ├── auth.ts            # Auth API calls
│   └── chat.ts            # Chat API (sessions, SSE streaming)  ← NEW
├── components/
│   ├── ChatInterface.tsx  # Floating chat widget                ← NEW
│   ├── PlanningChatDialog.tsx  # Multi-discussion planner       ← NEW
│   ├── AgileBoard.tsx     # Kanban board (+ planning dialog)
│   ├── Dashboard.tsx      # Overview
│   ├── InitiativeBoard.tsx
│   ├── KnowledgeGraph.tsx
│   ├── IdeaBoard.tsx
│   ├── DocumentVault.tsx
│   ├── FocusTimer.tsx
│   ├── LiveVoiceAssistant.tsx
│   ├── ScheduleView.tsx
│   ├── SpatialCanvas.tsx
│   ├── TeamManagement.tsx
│   └── CreationModals.tsx
├── contexts/
│   └── AuthContext.tsx    # User + workspace session state
├── hooks/
│   └── useChat.ts         # Chat state + SSE streaming logic    ← NEW
├── layouts/
│   ├── PersonalLayout.tsx # Mobile-first personal layout        ← UPDATED
│   └── CompanyLayout.tsx  # Mobile-first enterprise layout      ← UPDATED
├── pages/
│   ├── auth/LoginScreen.tsx
│   ├── auth/Onboarding.tsx
│   └── enterprise/AdminConsole.tsx
├── services/
│   ├── db.ts              # All REST API calls
│   ├── geminiService.ts   # Direct Gemini calls (legacy)
│   ├── analytics.ts       # Event tracking
│   └── orgService.ts      # Org API calls
├── types/index.ts         # TypeScript interfaces
├── config.ts              # API_BASE_URL
├── App.tsx                # Router + ChatInterface integration  ← UPDATED
└── main.tsx               # Vite entry point
```

### 5.2 State Management

| State | Owner | Purpose |
|-------|-------|---------|
| `user`, `workspace` | `AuthContext` | Session, persisted to localStorage |
| `companies` | `App.tsx` | Full workspace hierarchy |
| `messages`, `sessions` | `useChat` hook | Chat conversation state |
| Component UI state | Each component | Modals, tabs, forms |

### 5.3 Chat Architecture (Frontend)

```
useChat(workspaceId)
    ├── startNewSession()      → POST /chat/sessions
    ├── loadSession(id)        → GET /chat/sessions/{id}
    ├── sendMessage(content)   → POST /chat/sessions/{id}/messages (SSE)
    │       └── streamMessage() generator:
    │               ├── yield { type: 'chunk', content, node }
    │               ├── yield { type: 'tool_call', name }
    │               ├── yield { type: 'tool_result', name, result }
    │               └── yield { type: 'done', message_id }
    └── removeSession(id)      → DELETE /chat/sessions/{id}

ChatInterface (mounted globally in App.tsx)
    ├── Collapsed: floating Bot button (bottom-right)
    ├── Expanded: 400px panel (desktop) / full screen (mobile)
    ├── History sidebar: recent sessions
    └── Message list with:
            ├── Text bubbles (user/assistant)
            ├── Tool call pills (animated while running)
            └── Suggestion chips (empty state)

PlanningChatDialog (mounted per-project in AgileBoard)
    ├── Seeds conversation with project context
    ├── Multi-turn Q&A with planning agent
    ├── Quick reply suggestions
    └── Auto-detects task creation via tool_calls
```

### 5.4 Key Data Flows

**Chat message send flow:**
```
User types → sendMessage(content)
  → POST /chat/sessions/{id}/messages
  → Flask SSE stream begins
  → LangGraph router classifies intent
  → Appropriate agent runs with tools
  → Tool calls stream to UI (animated pills)
  → Text content streams chunk by chunk
  → done event → message persisted
  → UI updates message from streaming=true to complete
```

**Planning flow:**
```
User clicks "AI Plan" in AgileBoard
  → PlanningChatDialog opens
  → Seed message sent with project context
  → Planning agent starts in 'gathering' phase
  → Agent asks 2-3 clarifying questions
  → User answers in chat
  → Agent advances to 'drafting' → generates task list
  → User can request changes ("make X high priority")
  → Agent refines in 'refining' phase
  → User says "confirm"
  → Agent calls create_multiple_tasks tool
  → Tool creates tasks in DB
  → PlanningChatDialog detects tool call → calls onPlanExecuted()
  → AgileBoard refreshes tasks
```

---

## 6. MCP Server

File: `backend/app/mcp_server.py`

The MCP server exposes Sindhai workspace tools to **any MCP-compatible client**:
- Claude Desktop
- Claude Code (via MCP integration)
- Third-party AI agents

### 6.1 Available Tools

| Tool | Description |
|------|-------------|
| `sindhai_list_tasks` | List tasks with filters |
| `sindhai_create_task` | Create a single task |
| `sindhai_update_task` | Update task fields |
| `sindhai_delete_task` | Delete a task |
| `sindhai_create_project` | Create a project |
| `sindhai_get_workspace_summary` | Full workspace snapshot |
| `sindhai_analyze_progress` | Progress metrics |
| `sindhai_chat` | Send message to the agentic chat |

### 6.2 Running the MCP Server

```bash
# Set environment variables
export SINDHAI_API_BASE=https://sindhai.teams-lab.com
export SINDHAI_WORKSPACE_ID=your-workspace-id
export SINDHAI_TOKEN=your-jwt-token

# Run MCP server (connects via stdio)
python -m app.mcp_server --workspace-id <id> --token <jwt>
```

### 6.3 Claude Desktop Integration

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "sindhai": {
      "command": "python",
      "args": ["-m", "app.mcp_server"],
      "env": {
        "SINDHAI_WORKSPACE_ID": "your-workspace-id",
        "SINDHAI_TOKEN": "your-jwt-token",
        "SINDHAI_API_BASE": "https://sindhai.teams-lab.com"
      },
      "cwd": "/path/to/backend"
    }
  }
}
```

---

## 7. A2A (Agent-to-Agent) Protocol

Sindhai implements a subset of Google's A2A specification for inter-agent communication.

### 7.1 Agent Card

```
GET /.well-known/agent.json
```

Returns JSON-LD agent card with:
- Agent name, description, version
- Supported capabilities + skills
- Authentication method
- Endpoint URLs

### 7.2 Task Delegation

Other AI agents can delegate tasks to Sindhai:

```
POST /a2a/tasks/send
Authorization: Bearer <jwt>
{
  "id": "task-uuid",
  "message": {
    "role": "user",
    "parts": [{ "text": "Create 3 tasks for the authentication project" }]
  },
  "metadata": {
    "workspace_id": "ws-uuid"
  }
}
→ {
  "id": "task-uuid",
  "status": { "state": "completed" },
  "result": {
    "message": {
      "role": "agent",
      "parts": [{ "text": "I've created 3 tasks: ..." }]
    }
  }
}
```

### 7.3 Task Status Polling

```
GET /a2a/tasks/{task_id}
→ { "id": "...", "status": { "state": "completed" } }
```

---

## 8. Mobile-First Design

### 8.1 Layout Strategy

**PersonalLayout (mobile-first):**
- **Desktop** (≥ md): Fixed 256px sidebar + main content
- **Mobile** (< md):
  - Sidebar hidden by default (slide-in drawer on hamburger tap)
  - **Bottom navigation bar** with 6 core tabs (Home, Schedule, Graph, Ideas, Vault, Projects)
  - Overlay backdrop when sidebar open

**CompanyLayout (mobile-first):**
- Same pattern: sidebar on desktop, bottom nav on mobile
- Bottom nav: Admin, LMS, Projects

### 8.2 AgileBoard Mobile

- Kanban columns scroll horizontally with `snap-x snap-mandatory`
- Each column `min-w-[85vw]` on mobile → full-screen-ish card experience
- Swipe between columns naturally
- `active:scale-[0.98]` for touch feedback on cards

### 8.3 ChatInterface Mobile

- **Desktop**: 400px floating panel (bottom-right), expandable to 700px
- **Mobile**: Full-screen overlay with backdrop
- Input area stays at bottom with safe-area inset
- History sidebar hidden by default on mobile

### 8.4 Touch Targets

All interactive elements meet 44px minimum touch target (per WCAG 2.5.5):
- Nav buttons: `py-2.5` = 40px + text = ~44px
- Card action buttons: `p-2` inline + hover area expansion
- Bottom nav items: flex-1 with py-2 = 44px+ effective area

---

## 9. Multi-Discussion Planning

### 9.1 Planning Phase State Machine

```
gathering ──► drafting ──► refining ──► confirming ──► executed
    │                                        │
    └─────── user provides context ──────────┘
                                    │
                              user says "confirm"
                                    │
                                    ▼
                         create_multiple_tasks()
                                    │
                                    ▼
                        Tasks created in DB
```

### 9.2 Phase Behaviors

| Phase | Agent behavior | User action |
|-------|---------------|-------------|
| `gathering` | Asks 2-3 targeted questions | Answers context questions |
| `drafting` | Generates numbered task list with estimates | Reviews draft |
| `refining` | Applies user corrections to draft | "Make task 3 high priority", "Add a testing phase" |
| `confirming` | Presents final plan, asks for confirmation | "confirm" / "looks good" |
| `executed` | Calls `create_multiple_tasks` | Dialog closes, board refreshes |

### 9.3 Planning Context Seeding

The `PlanningChatDialog` auto-sends this seed message when opened:
```
I want to plan the project: "{projectName}" (type: {projectType}).
Context: {companyMission}
Project ID for task creation: {projectId}
Workspace ID: {workspaceId}

Please start the planning conversation by asking me the key questions
you need to build a great plan.
```

This grounds the planning agent with the project context before any user interaction.

### 9.4 Quick Replies

The dialog provides context-aware quick reply chips:
- "Looks good, confirm"
- "Make all high priority"
- "Add 2 more research tasks"
- "Shorten to 4 tasks"

These are pre-filled into the input (not auto-sent) so users can edit before sending.

---

## 10. Deployment Guide

### 10.1 Environment Variables

**Backend `.env`:**
```env
DATABASE_URL=postgresql://user:pass@host/sindhai
JWT_SECRET_KEY=your-secret-key-min-32-chars
API_KEY=your-google-gemini-api-key
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
```

**Frontend `.env.production`:**
```env
VITE_API_BASE_URL=https://your-backend-url.run.app
```

### 10.2 Database Setup

```bash
# Run migrations
psql $DATABASE_URL < database/schema.sql
psql $DATABASE_URL < database/v2_agentic_schema.sql
```

### 10.3 Backend Startup

```bash
pip install -r requirements.txt
gunicorn "app:create_app()" --workers 2 --timeout 120 --bind 0.0.0.0:$PORT
```

**Note:** SSE streaming requires `--timeout 120` or higher. Workers must use sync worker class (default).

### 10.4 Frontend Build

```bash
npm install
npm run build
# dist/ folder → deploy to Firebase Hosting or CDN
```

### 10.5 MCP Server Deployment

The MCP server runs as a standalone subprocess (stdio transport). For remote access, wrap in an HTTP adapter using FastMCP or mcp-server-http.

### 10.6 CORS Configuration

Update the origins list in `backend/app/__init__.py` when deploying to new domains.

### 10.7 Scaling Considerations

| Component | Scaling note |
|-----------|-------------|
| MemorySaver | In-memory → replace with PostgresSaver for multi-instance |
| SSE connections | Each stream holds a connection open; use gunicorn eventlet or gevent for high concurrency |
| LangGraph agents | Built fresh per request (stateless except checkpoints) |
| Gemini API | Subject to rate limits; add exponential backoff in production |

---

## Appendix A: Agent Prompt Templates

### Router
```
Classify intent into: crud | query | plan | analyze
Reply with ONLY the lowercase intent word.
```

### Query Agent
```
You are Sindhai's Query Intelligence with read-only access.
Answer accurately using tools. Format task lists clearly.
Never hallucinate IDs.
```

### CRUD Agent
```
You are Sindhai's Execution Engine.
1. Confirm every operation after execution.
2. State clearly what was deleted for destructive ops.
3. Use create_multiple_tasks for batches.
4. Look up IDs with get_projects/get_tasks first.
5. Report created/modified IDs for UI refresh.
```

### Analysis Agent
```
You are Sindhai's Strategic Analyst — elite Chief of Staff.
Provide: progress assessment, prioritized recommendations,
risk identification, concrete next steps.
Format as a structured briefing.
```

### Planning Agent
```
Guide users through: gathering → drafting → refining → confirming → executing.
Ask 2-3 targeted questions, generate 5-10 tasks, apply corrections,
execute when confirmed.
```

---

## Appendix B: New File Summary

| File | Purpose |
|------|---------|
| `database/v2_agentic_schema.sql` | New DB tables for chat and planning |
| `backend/app/agents/__init__.py` | Package init |
| `backend/app/agents/state.py` | LangGraph state TypedDicts |
| `backend/app/agents/tools.py` | All LangChain tool definitions |
| `backend/app/agents/orchestrator.py` | LangGraph multi-agent graph |
| `backend/app/api/chat.py` | Chat API endpoints + SSE streaming |
| `backend/app/mcp_server.py` | MCP server (stdio transport) |
| `frontend/src/api/chat.ts` | Chat API client + SSE reader |
| `frontend/src/hooks/useChat.ts` | Chat state management hook |
| `frontend/src/components/ChatInterface.tsx` | Floating chat widget |
| `frontend/src/components/PlanningChatDialog.tsx` | Multi-discussion planner |

## Appendix C: Modified File Summary

| File | Changes |
|------|---------|
| `backend/requirements.txt` | Added LangGraph, LangChain, MCP, ADK |
| `backend/app/__init__.py` | Registered chat blueprint + A2A endpoints |
| `frontend/src/App.tsx` | Added ChatInterface globally |
| `frontend/src/layouts/PersonalLayout.tsx` | Full mobile-first redesign + bottom nav |
| `frontend/src/layouts/CompanyLayout.tsx` | Full mobile-first redesign + bottom nav |
| `frontend/src/components/AgileBoard.tsx` | Replaced guidance modal with PlanningChatDialog |
