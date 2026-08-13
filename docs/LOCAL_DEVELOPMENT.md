# Local Development

## Prerequisites

- Python 3.11+.
- Node.js 20+.
- PostgreSQL.
- npm.

## Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Required local env keys:

```text
DATABASE_URL
SECRET_KEY
JWT_SECRET_KEY
FRONTEND_BASE_URL
```

Use a disposable database for tests:

```bash
export TEST_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ora_test_pytest
```

Run migrations and server:

```bash
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db upgrade
python run.py
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Production builds use relative API URLs by default so Firebase Hosting can rewrite
`/api/**` to Cloud Run.

## Tests

```bash
cd backend
AUTO_CREATE_TABLES=false .venv/bin/pytest -q

cd frontend
npm run test
npm run typecheck
npm run build
```

## Visual Audit

When a dev server is running:

```bash
cd frontend
ORA_VISUAL_URL=http://127.0.0.1:3000/ node scripts/visual-audit.mjs
```
