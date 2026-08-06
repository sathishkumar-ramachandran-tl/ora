# Ora — Technical Documentation

This is the single source of truth for the codebase: backend, frontend, and database.
It supersedes and replaces `ARCHITECTURE_2.0.md`, `FRONTEND_BUILD_GUIDE.md`,
`ORA_CORTEX_v2_ARCHITECTURE.md`, `frontend/ARCHITECTURE.md`,
`frontend/PRODUCT_SPECS.md`, `frontend/README.md`, and `frontend/WEBSITE_DESIGN.md`,
all of which described an earlier pre-reorg prototype and have been removed.

## Contents

1. [Product overview](#product-overview)
2. [Repository layout](#repository-layout)
3. [Backend](#backend)
4. [Database](#database)
5. [Frontend](#frontend)
6. [Local development](#local-development)
7. [Testing](#testing)

---

## Product overview

Ora is an agentic productivity platform for freelancers, startup founders, students,
and content creators, unified under one interface that switches between a **Personal**
and a **Company/Organization** persona. The core bet: the AI *acts* on the user's behalf
(creates tasks, drafts plans, manages access) rather than just organizing information —
a LangGraph multi-agent orchestrator sits behind chat, exposed identically to both an
in-app chat UI and an MCP server for external agent clients.

---

## Repository layout

```
backend/
  app/
    core/           # config, db/jwt/cors extensions, logging, security primitives, authz
    auth/            # registration, login, OAuth (Google/Microsoft), email verification, password reset
    organizations/   # Organization, agentic RBAC (CustomRole, permissions, rbac_tools.py)
    billing/         # Plan, Subscription, overrides, promo codes, Stripe, usage limits
    workspaces/      # Workspace (personal/company), WorkspaceMember
    projects/        # Company, Project, Milestone, Sprint, TaskDependency
    tasks/           # Task
    notes/ documents/ calendar/ analytics/   # supporting domains
    chat/            # ChatSession/ChatMessage + SSE streaming endpoint
    agents/          # LangGraph orchestrator, tool registry wrappers, LLM call tracking
    tools/           # shared {success, data, error} business-logic functions,
                      # called by both agents/tools.py (LangChain) and mcp_server.py (MCP)
    mcp_server.py    # MCP protocol server, thin wrappers over app/tools/
  migrations/        # Alembic
  tests/             # pytest, one file per domain

frontend/
  src/
    api/             # resource-scoped HTTP clients (auth, org, workspace, tasks, projects, ...)
    pages/           # route-level screens (auth/, enterprise/, ...)
    layouts/         # PersonalLayout, CompanyLayout shells
    components/      # AgileBoard, ScheduleView, IdeaBoard, KnowledgeGraph, ...
    contexts/        # AuthContext
    hooks/           # useChat (SSE), etc.
    styles/           # design tokens
    types/           # shared TS types
```

---

## Backend

**Stack:** Flask + SQLAlchemy + PostgreSQL, Flask-JWT-Extended, Authlib (OAuth2),
boto3 (SES), Stripe, LangGraph + `langchain_google_genai` (Gemini).

### Domain package convention

Every domain package (`auth/`, `organizations/`, `billing/`, `workspaces/`, `projects/`,
`tasks/`, ...) follows the same shape:

- `models.py` — SQLAlchemy models for that domain
- `routes.py` — Flask blueprint
- `service.py` / `*_tools.py` (where relevant) — business logic separated from HTTP

`app/models.py` is a thin re-export aggregator importing every domain's models, so
`db.create_all()`/Alembic autogenerate sees the full schema regardless of import order.

### Auth (`app/auth/`)

- Username + password (pbkdf2:sha256 via `werkzeug.security`) and OAuth (Google,
  Microsoft — both via Authlib's OpenID Connect discovery).
- New-user email verification and forgot-password both use a 6-digit OTP /
  random-token flow (`EmailVerificationToken`, `PasswordResetToken`), sent via Amazon
  SES (`app/core/email.py`) — not the user's personal credentials.
- A welcome email fires once, at the moment a user completes onboarding
  (`complete_onboarding_if_needed`), not at raw registration.
- JWT access tokens (1h expiry) issued on register/login/OAuth callback.
- `app/core/config.py` requires `SECRET_KEY`, `JWT_SECRET_KEY`, and `DATABASE_URL` to be
  set in the environment — there is no hardcoded fallback for any of them. The app
  refuses to boot if they're missing (fail-fast, not a silently insecure default).

### Organizations & agentic RBAC (`app/organizations/`)

- `Organization` — the Company/Institution context, created alongside a company
  `Workspace` (Onboarding always creates the `Organization` first, since a workspace's
  `organization_id` is required — this is what makes the Company/Org admin console work
  instead of coming up empty).
- `CustomRole` — organization-scoped, holds a JSONB list of granular permission strings
  from the catalog in `permissions.py` (`org.manage_roles`, `project.view_financials`,
  `task.approve`, etc. — 18 total). Three system roles (Admin/Member/Viewer) are seeded
  on org creation.
- **Agentic RBAC** (`rbac_tools.py`): every mutation (create/update/delete role, assign
  role, grant/revoke a single permission) is exposed as a plain function the LangGraph
  orchestrator and MCP server can both call, so an admin can manage access via natural
  language ("give Priya project financials but not billing"). Security invariant: every
  mutating function takes `acting_user_id` and re-checks that user's own
  `org.manage_roles` permission before doing anything — the agent can never grant more
  access than the requesting human already has. Covered by
  `test_agentic_grant_permission_requires_caller_to_already_have_manage_roles`.
- The Owner tier is intentionally unrestricted (never permission-limited) so an org can
  never be locked out of its own data by a role-editing mistake, including one the AI
  makes.

### Billing (`app/billing/`)

- 5 launch tiers (Free Trial, Student, Freelancer, Startup, Enterprise), seeded into a
  `plans` table with limits stored as JSONB — not hardcoded in Python, so a platform
  admin can tune them via `PATCH /api/v2/billing/admin/plans/<id>` without a deploy.
- `Subscription` — one per personal user or per organization; auto-created on
  registration/OAuth signup/org creation as a trial (default 45 days, itself an
  admin-adjustable `PlatformSetting`, and extendable per-subscription).
- `PlanOverride` — the special-access/marketing lever: a platform admin grants a
  subscription a partial limit override (e.g. unlimited AI calls for 90 days for a beta
  partner), time-boxed or permanent, layered on top of the plan's defaults.
- `PromoCode` — self-serve codes a user redeems for a trial extension or plan upgrade
  (single-use per subscription, optional max-redemption cap).
- Stripe Checkout/Billing Portal/webhook routes — fail gracefully (503, not a crash)
  until `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` are configured.
- Limit enforcement: `check_limit()` compares live usage (workspaces/projects/tasks/AI
  calls this month/team members/custom roles) against the subscription's effective
  limits; wired into workspace creation today (`402 limit_reached` once hit).

### Core Intelligence Layer / agents (`app/agents/`)

- `orchestrator.py` — LangGraph `StateGraph`: `router_node` classifies intent
  (`query|crud|plan|analyze`) and dispatches to one of four `create_react_agent` nodes,
  each bound to a workspace-scoped tool subset. `planning_node` persists multi-turn
  planning phase (`gathering → drafting → refining → confirming → executed`) via the
  Postgres-backed checkpointer (`checkpointer.py`, `langgraph.checkpoint.postgres`), so
  state survives restarts and is shared across workers.
- **LLM call tracking** (`llm_tracking.py`): a LangChain callback (`LlmUsageCallback`)
  attached to every node's model invocation — including the internal tool-call/response
  round-trips inside a `create_react_agent` loop, not just the top-level call. Writes
  one `LlmCall` row per raw model call: provider, model, node, prompt/completion/total
  tokens, an estimated USD cost, latency, and success/error status. Surfaced via
  `GET /api/v1/agents/llm-usage?workspace_id=`.
- `app/tools/` — the single shared registry of business-logic functions
  (`task_tools.py`, etc.), each returning a canonical `{success, data, error}` shape.
  `app/agents/tools.py` wraps these as LangChain `@tool`s; `app/mcp_server.py` wraps the
  *same* functions as MCP `Tool`s — the two catalogs can't drift because they call
  identical code, covered by `tests/test_tool_registry.py` and `test_mcp_server.py`.

### Logging (`app/core/logging.py`)

- Structured JSON logs by default (`LOG_FORMAT=json`; `console` for local dev), one line
  per event.
- Every request gets a `request_id` (propagated from an incoming `X-Request-ID` header,
  or generated) attached to every log line for that request and echoed back in the
  response header — traceable end-to-end: HTTP request → LLM call → tool call.
- A global `@app.errorhandler(Exception)` guarantees every uncaught 500 is logged with a
  full stack trace as structured JSON before the client sees a generic error — Flask's
  default unlogged HTML traceback page never reaches a caller.
- Security-relevant events are logged explicitly beyond the generic request line:
  login success/failure, registration, every RBAC role/permission mutation
  (`rbac_role_created`, `rbac_permission_granted`, etc.), and billing admin actions
  (plan changes, trial extensions, override grants).

### Authorization (`app/core/authz.py`)

- `user_can_access_workspace(user_id, workspace_id)` is the baseline gate for any
  resource hanging off a `workspace_id` (tasks, projects, notes, documents, calendar
  events): true if the user is the workspace's personal owner, a `WorkspaceMember`, or
  an active member of the owning `Organization` (for company workspaces). Applied
  uniformly across the CRUD routes in `tasks/`, `projects/`, `notes/`, `documents/`,
  `calendar/`, and `workspaces/` — see `tests/test_authz.py`.

### Security notes

- Password hashing: `pbkdf2:sha256` via `werkzeug.security`.
- Tokens (email verification, password reset): `secrets.token_urlsafe(32)`.
- `SECRET_KEY`/`JWT_SECRET_KEY`/`DATABASE_URL` have no hardcoded fallback — the app
  refuses to boot without them explicitly set.
- OAuth state/PKCE/nonce validation is handled by Authlib, not hand-rolled.
- Forgot-password never reveals whether an email exists (`POST /forgot-password` always
  returns `{"status": "sent"}`).

---

## Database

PostgreSQL via SQLAlchemy, migrations via Alembic (`backend/migrations/`). Tables are
grouped by the domain package that owns them:

| Domain | Tables |
|---|---|
| Auth | `users`, `oauth_accounts`, `email_verification_tokens`, `password_reset_tokens` |
| Organizations | `organizations`, `organization_members`, `custom_roles` |
| Billing | `plans`, `subscriptions`, `plan_overrides`, `promo_codes`, `promo_redemptions`, `platform_settings` |
| Workspaces | `workspaces`, `workspace_members` |
| Projects | `companies`, `projects`, `project_members`, `milestones`, `sprints`, `task_dependencies` |
| Tasks | `tasks` |
| Notes / Documents / Calendar / Analytics | `notes`, `documents`, `calendar_events`, `activity_logs` |
| Chat | `chat_sessions`, `chat_messages` |
| Agents | `agent_tool_calls`, `planning_sessions`, `llm_calls` |

Notable design choices:

- `CustomRole.permissions` and `Plan.limits` are JSONB, not fixed columns — both are
  meant to be tuned (by an org admin or platform admin, respectively) without a schema
  migration.
- `LlmCall` and `AgentToolCall` are separate: `AgentToolCall` logs a *tool* invocation,
  `LlmCall` logs a raw *model* call — a single agent turn can involve multiple LLM calls
  (one that decides to call a tool, one that processes the result) around one tool call.
- `Subscription` has a `CHECK` constraint enforcing exactly one of `user_id` /
  `organization_id` is set — a subscription belongs to a person or an org, never both,
  never neither.
- Foreign keys carry explicit names (e.g. `fk_organization_members_custom_role_id`) for
  Postgres compatibility with Alembic's constraint-drop autogeneration.

Migrations are linear (`add_new_columns_001 → 7b1375f2a1b6 → 45708d7771bc →
8cb7513702a4`, one head). Run `flask db upgrade` to bring a database to the latest
schema; `flask db migrate -m "..."` to generate a new one after a model change (run with
`AUTO_CREATE_TABLES=false` so the dev-convenience `db.create_all()` doesn't pollute the
autogenerate diff).

---

## Frontend

**Stack:** React 19 + TypeScript + Vite, Tailwind (+ `tailwindcss-animate`), Vitest +
React Testing Library.

### Structure

- `api/*.ts` — one file per backend resource (`auth.ts`, `org.ts`, `workspace.ts`,
  `tasks.ts`, `projects.ts`, `calendar.ts`, `modules.ts`), all going through
  `api/client.ts` as the single transport layer. `api/chat.ts` (SSE) stays separate.
- `pages/auth/` — `LoginScreen` (login/register/forgot modes + Google/Microsoft OAuth
  buttons), `VerifyEmailScreen` (OTP entry), `OAuthCallback` (captures `?token=` from the
  redirect), `ResetPassword` (captures `?token=`, sets new password), `Onboarding`.
- `pages/enterprise/AdminConsole.tsx` — the Company/Org admin console: **Members &
  Access** (real org members, coarse role + custom role dropdown, invite form),
  **Roles & Permissions** (CustomRole list + editor built from the live permission
  catalog), **Settings**.
- `layouts/PersonalLayout.tsx` / `CompanyLayout.tsx` — the two persona shells; nav
  structure and labels differ per persona, styling doesn't.
- `contexts/AuthContext.tsx` — holds the current user, exposes `login`/`logout`/
  `refreshUser`.
- `App.tsx` — top-level `<Routes>` for `/oauth/callback`, `/reset-password`, and a
  catch-all into the existing tab-state app; gates on `user.email_verified` (renders
  `VerifyEmailScreen` if false); loads the real `Organization` for company-context
  workspaces via `getMyOrganizations()` (no more mock org data).

### Design tokens (`styles/`)

Palette: Deep Slate `#0f172a`, Electric Indigo `#4f46e5`, Neural Emerald `#10b981`;
`Inter` font; glow box-shadows; a real Tailwind `keyframes`/`animation` scale (the
`animate-in fade-in zoom-in-95` classes used throughout the app require
`tailwindcss-animate`, which is installed). Exported as raw values too, for D3
(`KnowledgeGraph.tsx`) and canvas (`SpatialCanvas.tsx`) consumers that can't use
Tailwind classes directly.

### Type safety

`tsc --noEmit` is a `package.json` script (`npm run typecheck`) — Vite doesn't
type-check on serve, so this is the only thing that catches type drift before it ships.

---

## Local development

**Backend:**

```bash
cd backend
cp .env.example .env   # fill in DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY at minimum
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask db upgrade
python run.py           # serves on :5050 (macOS reserves :5000 for AirPlay Receiver; override with PORT env var)
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev              # serves on :5173 (or configured port)
```

Required environment variables are documented in `backend/.env.example` — at minimum
`DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`. Everything else (SES, OAuth, Stripe)
degrades gracefully when unset (features requiring it return a clear error instead of
crashing).

---

## Testing

**Backend:** `cd backend && pytest` — one file per domain (`test_auth.py`,
`test_rbac.py`, `test_billing.py`, `test_llm_tracking.py`, `test_authz.py`,
`test_tool_registry.py`). Uses a real disposable Postgres database
(`TEST_DATABASE_URL`, defaults to a local `ora_test` DB), with
`create_all()`/`drop_all()` per test via `tests/conftest.py`.

**Frontend:** `cd frontend && npm run typecheck && npm test` (Vitest).
