# Ora — The Operating System for High-Velocity Ambition

> One AI-native workspace. Every project, plan, and thought. Nothing slips.

Ora is an **AI-native project and knowledge management platform** for founders,
researchers, students, and freelancers who juggle multiple domains of work at once.
Instead of switching between Jira (tasks), Notion (notes), Miro (planning), and a
stateless AI chat tool, Ora unifies all of it behind one agentic interface: the AI
reads your workspace, executes actions, plans projects, and analyzes progress — it
doesn't just suggest, it acts.

For full technical documentation (backend architecture, database schema, frontend
structure, environment setup, testing), see **[DOCUMENTATION.md](DOCUMENTATION.md)**.

## Who it's for

| Persona | Pain point Ora solves |
|---|---|
| Founder / Entrepreneur | Balancing fundraising strategy with product execution |
| PhD Researcher | Managing papers, grants, experiments, and deadlines |
| Product Executive | Stakeholder alignment and roadmapping without five separate tools |
| Elite Student | Optimizing learning across courses, projects, and extracurriculars |
| Freelancer | Juggling multiple clients, billing contexts, and independent projects |
| Startup team | Company-wide project management with real RBAC and billing |

## What makes it different

- **Multi-agent AI (Ora Cortex)** — a LangGraph-orchestrated router + query/CRUD/
  planning/analysis agents, all sharing workspace state, streaming over SSE with live
  tool-call visibility. Every LLM call is tracked (tokens, cost, latency) for
  observability.
- **Agentic RBAC** — organization admins manage granular custom roles and permissions
  through natural language, not just a settings form, with a hard security invariant:
  the AI can never grant more access than the requesting human already has.
- **Neural Knowledge Graph** — a D3.js force-directed graph rendering your entire
  workspace as a living map.
- **A2A + MCP protocols** — Ora is both an Agent-to-Agent client/server and an
  MCP-compatible server, so external agent clients (Claude, Cursor, custom agents) can
  discover and act on workspace data through the same tool registry the in-app chat
  uses.
- **Billing built in** — Free Trial / Student / Freelancer / Startup / Enterprise tiers
  with admin-adjustable limits, Stripe checkout, and a special-access override
  mechanism for partners/beta users.

## Quickstart

```bash
# Backend
cd backend
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY at minimum
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask db upgrade
python run.py            # :5050 (override with PORT env var)

# Frontend
cd frontend
npm install
npm run dev               # :5173
```

See [DOCUMENTATION.md](DOCUMENTATION.md) for the full environment variable reference,
architecture deep-dive, and how to run the test suites.

## Design philosophy

1. **AI that acts, not just advises** — every agent has real write access.
2. **One mental model** — users shouldn't need to leave the app to get work done.
3. **Persona awareness** — the platform adapts to who you are, not the reverse.
4. **Transparent AI** — every agent action is visible in the chat UI.
5. **Speed over ceremony** — capture first, organize later.
