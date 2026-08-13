# Deployment

Deployment is gated. Do not deploy when tests, security audits, Git state, production
targets, database backup, or migrations are uncertain.

## Known Targets

- GCP/Firebase project: `ora-teamslab`
- Cloud Run service: `ora-backend`
- Region: `asia-south1`
- Firebase Hosting site/project alias: `ora-teamslab`

## Current Gate Status

During the readiness pass, the configured database was at revision `49c02f01de53` while
the repo head was `a6c8f2d4e901`. Production deployment is blocked until backup/recovery
is confirmed and migrations are run successfully.

## Backend Preflight

```bash
git status --short --branch
cd backend
AUTO_CREATE_TABLES=false .venv/bin/pytest -q
.venv/bin/pip-audit -r requirements.txt
.venv/bin/bandit -r app -x '*/__pycache__/*'
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db current
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db heads
```

## Frontend Preflight

```bash
cd frontend
npm run test
npm run typecheck
npm run build
npm audit
```

## Database Migration

Only after backup/recovery is confirmed:

```bash
cd backend
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db upgrade
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db current
```

## Backend Deploy

Use the repository's existing Cloud Run image deployment path:

```bash
cd backend
docker build --platform linux/amd64 -t asia-south1-docker.pkg.dev/ora-teamslab/cloud-run-source-deploy/ora-backend:<sha> .
docker push asia-south1-docker.pkg.dev/ora-teamslab/cloud-run-source-deploy/ora-backend:<sha>
gcloud run deploy ora-backend \
  --image asia-south1-docker.pkg.dev/ora-teamslab/cloud-run-source-deploy/ora-backend:<sha> \
  --project ora-teamslab --region asia-south1
```

Do not print secrets. Confirm Cloud Run env vars/secrets before deploy.

## Frontend Deploy

```bash
cd frontend
npm run build
npx firebase-tools deploy --only hosting --project ora-teamslab
```

## Rollback

- Backend: route traffic back to the previous known-good Cloud Run revision.
- Frontend: rollback/redeploy the previous Firebase Hosting release.
- Database: do not assume app rollback rolls back schema. Check migration compatibility.
