# Sindhai — The Operating System for High-Velocity Ambition

> **Tagline:** One AI-native workspace. Every project, plan, and thought. Nothing slips.

---

## What Is Sindhai?

Sindhai is an **AI-native project and knowledge management platform** built for ambitious individuals — founders, researchers, students, and freelancers — who manage multiple domains of work simultaneously and need more than a task tracker.

Where traditional tools force you to context-switch between Jira (tasks), Notion (notes), Miro (planning), and separate AI chat tools, Sindhai unifies all of it behind a single intelligent interface. The AI doesn't just generate suggestions — it **reads your workspace, executes actions, plans projects, and analyzes progress** as a true agentic collaborator.

Think of it as: **Jira + Notion + AI Chief of Staff, in one tab.**

---

## Who Is It For?

Sindhai is designed for people carrying multiple ambitious workstreams at once:

| Persona | Pain Point Sindhai Solves |
|---------|--------------------------|
| **Founder / Entrepreneur** | Balancing fundraising strategy with product execution, losing track of initiatives |
| **PhD Researcher** | Managing papers, grants, experiments, and deadlines across unstructured work |
| **Product Executive** | Stakeholder alignment, roadmapping, and team execution without five separate tools |
| **Elite Student** | Optimizing learning across courses, projects, and extracurriculars |
| **Freelancer** | Juggling multiple clients, billing contexts, and independent projects |
| **Software Engineer** | Side projects, hackathons, and professional work in parallel |
| **Writer / Creator** | Research, drafting, revision tracking, and publishing workflow |
| **UPSC / Competitive Exam Aspirant** | Structured long-term study planning with AI guidance |

---

## The Problem It Solves

### Productivity Stack Fragmentation

Modern ambitious people maintain 5–8 separate tools that don't talk to each other:

```
Jira        →  task tracking
Notion      →  notes and docs
Miro        →  visual planning
Google Cal  →  scheduling
ChatGPT     →  idea generation (no context, no memory)
Slack       →  communication
Drive       →  document storage
```

Every context switch costs cognitive energy. Every tool has a different mental model. AI tools like ChatGPT are stateless — they can't see your tasks, can't create them, and have no memory of your workspace.

### What Sindhai Does Instead

Sindhai collapses this entire stack into one workspace where:
- Your **AI knows your entire workspace** (projects, tasks, initiatives, priorities)
- The **AI takes real actions** — creates tasks, updates statuses, plans projects
- Your **knowledge is connected** — notes link to projects, ideas promote to initiatives
- Your **time is managed** — AI auto-schedules tasks onto your calendar
- Everything lives in **one place with one mental model**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    REACT FRONTEND (Vite + TS)                │
│   PersonalLayout │ CompanyLayout │ ChatInterface (floating)  │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST + SSE
┌──────────────────────────▼──────────────────────────────────┐
│                   FLASK API (Blueprints)                      │
│   /api/v1/* (core)  │  /api/v2/* (enterprise)  │ /chat/*    │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              MULTI-AGENT LAYER (LangGraph)                    │
│                                                               │
│     ┌─────────────── router_node ───────────────┐            │
│     │     Intent classification (Gemini Flash)   │            │
│     └───┬──────────┬─────────────┬──────────────┘            │
│         │          │             │              │             │
│   query_agent  crud_agent  planning_agent  analysis_agent     │
│   (read/search) (mutations) (multi-turn)   (insights)         │
└──────────────────────────┬──────────────────────────────────┘
                           │ SQLAlchemy
┌──────────────────────────▼──────────────────────────────────┐
│              POSTGRESQL (Neon serverless)                     │
│   users · workspaces · companies · projects · tasks          │
│   notes · events · chat_sessions · chat_messages             │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| Styling | TailwindCSS + Lucide React |
| Backend | Flask 3.0 + SQLAlchemy |
| Database | PostgreSQL via Neon (serverless) |
| Auth | JWT + Gmail API (OTP, passwordless) |
| Agentic AI | LangGraph 0.2+ multi-agent orchestration |
| LLM | Google Gemini (Flash + Pro via LangChain) |
| Streaming | SSE (Server-Sent Events) |
| Protocols | REST, SSE, MCP, A2A |
| Deployment | GCP Cloud Run + Docker |

---

## Unique Features

### 1. Multi-Agent AI — Sindhai Cortex
A LangGraph-orchestrated system of four specialized agents, all sharing workspace state:

- **Router Agent** — classifies intent (`query`, `crud`, `plan`, `analyze`) in real-time
- **Query Agent** — reads, searches, and lists workspace data; answers questions with real data
- **CRUD Agent** — creates, updates, and deletes tasks/projects/initiatives from conversation
- **Planning Agent** — multi-turn project planning across five phases: gathering → drafting → refining → confirming → executing
- **Analysis Agent** — strategic analysis, bottleneck detection, prioritization, and weekly briefings

Every response **streams via SSE** with live tool-call visibility in the chat UI.

### 2. Neural Knowledge Graph
A D3.js force-directed graph that renders your **entire workspace as a living map** — every initiative, project, and task as nodes. Node size reflects task density; node glow indicates completion. Lets you see the full shape of your work at a glance.

### 3. AI Auto-Schedule (Resource Allocation)
The Schedule view lets the AI **automatically assign time blocks** to unscheduled tasks on your calendar. The AI considers task priority, estimated hours, and existing blocks to suggest an optimal daily schedule, which you can accept or reject in one click.

### 4. Idea Incubator → Strategic Initiative
Capture raw thoughts as sticky notes. A single **"Promote" action** converts any note into a full Strategic Initiative (Initiative + Project + mission statement), instantly elevating a passing idea into tracked, structured work.

### 5. Persona-Aware Intelligence
The platform adapts its AI behavior, terminology, and suggestions based on your selected persona. A PhD researcher gets different planning scaffolding than a startup founder or a competitive exam student.

### 6. A2A Protocol (Agent-to-Agent)
Sindhai implements Google's **Agent-to-Agent (A2A) specification** — a standardized JSON-LD protocol that lets external AI agents discover Sindhai's capabilities, delegate tasks to it, and receive structured results. Sindhai acts as both an A2A client and server.

### 7. MCP Server (Model Context Protocol)
An MCP-compatible server exposes Sindhai's workspace data and tools to any MCP-enabled AI client (Claude, Cursor, custom agents), enabling external tools to read and act on your workspace.

### 8. Document Vault
Encrypted document storage co-located with your projects. Pitch decks, research papers, contracts, and reference material live next to the tasks that use them — no switching to Drive.

### 9. Focus Timer (Deep Work Mode)
A built-in Pomodoro-style focus timer that locks onto a specific task. Tracks active focus time per task and surfaces it in the analytics layer.

### 10. Live Voice Assistant
Real-time voice interaction layer for hands-free workspace control — query tasks, capture ideas, or update statuses without touching the keyboard.

---

## Full Feature List

### Workspace & Organization
- Multi-workspace support (personal and company contexts)
- Strategic Initiatives (called Companies/Domains internally) with missions and colors
- Projects with typed contexts: `build`, `learning`, `client`, `research`, `campaign`
- Workspace full-state sync on load
- Team management with custom RBAC roles and permission sets
- Organization-level hierarchy for enterprise contexts

### Task & Project Management
- Agile kanban board (statuses: backlog → todo → in-progress → review → done)
- Task priorities: low, medium, high, critical
- Task estimated hours and assignee fields
- Task resource attachments (links and file references)
- Bulk task creation from AI planning
- Daily Focus mode — mark and surface the day's priority tasks

### AI (Sindhai Cortex)
- Multi-agent chat with streaming SSE responses
- Real-time tool-call transparency in the chat UI
- Intent-based routing (query / crud / plan / analyze)
- Persistent conversation history per session
- Workspace-grounded context injection into every agent call
- Multi-turn project planning agent (5-phase flow)
- AI executive summary / weekly briefing
- AI schedule optimization (auto-calendar blocking)
- Strategic analysis with bottleneck and risk detection

### Visualization
- D3.js Neural Knowledge Graph (force-directed, live progress)
- Monthly and daily calendar views
- Agile board with drag-and-drop
- Spatial Canvas (infinite whiteboard per project)

### Communication & Auth
- Passwordless OTP authentication via Gmail API
- JWT session tokens (7-day expiry)
- Real-time SSE streaming for all agent responses

### Developer / Integration
- MCP server for external AI tool access
- A2A protocol for agent delegation and discovery (`/.well-known/agent.json`)
- REST API v1 (core), v2 (enterprise), and `/chat` (agentic)
- Analytics event tracking pipeline

---

## Project Structure

```
application/
├── frontend/               # React + Vite SPA
│   ├── src/
│   │   ├── components/     # UI components (Dashboard, AgileBoard, ChatInterface, …)
│   │   ├── hooks/          # useChat, custom hooks
│   │   ├── api/            # API client functions (chat.ts, auth.ts, …)
│   │   ├── services/       # db.ts (REST calls), geminiService.ts
│   │   ├── contexts/       # AuthContext
│   │   └── types/          # TypeScript interfaces
│   ├── .env.local          # VITE_API_BASE_URL
│   └── vite.config.ts
│
├── backend/                # Flask API + LangGraph agents
│   ├── app/
│   │   ├── __init__.py     # App factory, blueprint registration, A2A endpoints
│   │   ├── config.py       # Config class, load_dotenv
│   │   ├── models.py       # SQLAlchemy models
│   │   ├── routes.py       # Core auth + workspace + agent blueprints
│   │   ├── agents/
│   │   │   ├── orchestrator.py  # LangGraph graph, router + agent nodes
│   │   │   ├── tools.py         # LangChain @tool definitions (CRUD + READ)
│   │   │   └── state.py         # AgentState TypedDict
│   │   ├── api/
│   │   │   ├── chat.py          # SSE streaming chat endpoint
│   │   │   ├── workspace.py     # Workspace API v2
│   │   │   └── org.py           # Organization API v2
│   │   └── mcp_server.py        # MCP server definition
│   ├── .env                # API_KEY, SECRET_KEY, DATABASE_URL
│   ├── run.py              # Entry point
│   └── requirements.txt
│
└── database/               # SQL migrations and schema
```

---

## Environment Setup

### Backend `.env`
```env
SECRET_KEY=your-flask-secret
JWT_SECRET_KEY=your-jwt-secret
DATABASE_URL=postgresql+psycopg://user:pass@host/db
API_KEY=your-google-gemini-api-key
MAIL_USERNAME=your-gmail-address
MAIL_PASSWORD=your-gmail-app-password
```

### Frontend `.env.local`
```env
VITE_API_BASE_URL=http://localhost:5000
```

### Running Locally
```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python run.py

# Frontend
cd frontend
npm install
npm run dev
```

---

## AI Agent Capabilities

The Sindhai Cortex chat understands natural language and routes to the right agent automatically:

| What you say | Agent used | What happens |
|-------------|-----------|-------------|
| "Show me all my pending tasks" | Query Agent | Lists tasks from your workspace |
| "Create a task: Review API docs, high priority" | CRUD Agent | Creates the task in your project |
| "Help me plan a new mobile app project" | Planning Agent | Starts 5-phase multi-turn planning |
| "Analyze my workspace and tell me what to focus on" | Analysis Agent | Full strategic briefing |
| "Mark the API docs task as done" | CRUD Agent | Updates task status |
| "What's the progress on the Hackathon project?" | Query Agent | Reads and summarizes project data |

---

## Design Philosophy

1. **AI that acts, not just advises** — Every agent has real write access. The AI can create tasks, not just suggest them.
2. **One mental model** — Users should never need to leave the app to accomplish a work-related action.
3. **Persona awareness** — The platform adapts to who you are and how you work, not the other way around.
4. **Transparent AI** — Every agent action is visible in the chat UI. Users always know what the AI did and why.
5. **Speed over ceremony** — Capture first, organize later. Promote ideas instantly. Plan projects in conversation.
