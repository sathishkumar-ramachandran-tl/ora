# Database

Ora uses PostgreSQL with SQLAlchemy models and Alembic migrations.

## Commands

```bash
cd backend
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db current
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db heads
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db history
AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db upgrade
```

`AUTO_CREATE_TABLES=false` is required for migration work. Application startup no
longer creates tables by default; schema changes belong in Alembic.

## Current Migration Chain

The current repository has one Alembic head:

```text
a6c8f2d4e901
```

The configured database inspected during the readiness pass reported:

```text
current revision: 49c02f01de53
target revision:  a6c8f2d4e901
migration required: YES
```

## Production Migration Policy

Before running a production migration:

1. Confirm the target Cloud Run/Firebase release SHA.
2. Confirm the production database connection target without printing credentials.
3. Confirm backup/recovery capability.
4. Run read-only prechecks.
5. Run `AUTO_CREATE_TABLES=false FLASK_APP=run.py flask db upgrade`.
6. Verify `flask db current` equals the target head.
7. Deploy backend only after migration succeeds.

Read-only prechecks:

```sql
select version_num from alembic_version;
select count(*) from workspace_members where workspace_id is null or user_id is null;
select count(*) from tasks t left join workspaces w on w.id = t.workspace_id where w.id is null;
select count(*) from projects p left join workspaces w on w.id = p.workspace_id where w.id is null;
select count(*) from calendar_events e left join workspaces w on w.id = e.workspace_id where w.id is null;
```

## Rollback

Prefer backward-compatible migrations. Application rollback does not automatically roll
back the database. If a migration is not backward-compatible, document the exact
downgrade and data-loss risk before production deployment.
