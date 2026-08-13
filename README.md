# Ora

Ora is an agentic productivity workspace for personal work and company/team execution.
It combines projects, tasks, calendar scheduling, chat, planning proposals, research
evidence, documents, workspace search, and RBAC-backed team administration behind a
Flask API and a React/Vite frontend.

## Architecture

- Backend: Flask, SQLAlchemy, PostgreSQL, Alembic, JWT auth, LangGraph/LangChain agent
  orchestration, Cloud Run deployment.
- Frontend: React, TypeScript, Vite, Tailwind, Firebase Hosting.
- Database: PostgreSQL with a linear Alembic migration chain.
- Auth: bearer JWTs stored by the frontend and verified by every protected backend
  endpoint.

## Repository Layout

```text
backend/
  app/
    auth/ calendar/ chat/ documents/ organizations/ projects/ tasks/ workspaces/
    agents/ tools/ core/
  migrations/
  tests/
frontend/
  src/
    api/ components/ contexts/ features/ hooks/ layouts/ pages/ styles/ types/
  scripts/
docs/
```

## Quick Start

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db upgrade
python run.py
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Test Commands

```bash
cd backend && AUTO_CREATE_TABLES=false .venv/bin/pytest -q
cd backend && .venv/bin/pip-audit -r requirements.txt
cd backend && .venv/bin/bandit -r app -x '*/__pycache__/*'
cd frontend && npm run test
cd frontend && npm run typecheck
cd frontend && npm run build
cd frontend && npm audit
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Local Development](docs/LOCAL_DEVELOPMENT.md)
- [Database](docs/DATABASE.md)
- [Security](docs/SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Operations](docs/OPERATIONS.md)
- [API Overview](docs/API_OVERVIEW.md)
- [Release Checklist](docs/RELEASE_CHECKLIST.md)
- [Security Verification](docs/SECURITY_VERIFICATION.md)

Production deployment must follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). Do not
deploy when the database migration, backup, Git, or security gates are unresolved.
