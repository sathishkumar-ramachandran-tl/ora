# Release Checklist

- [ ] Git branch and remote verified.
- [ ] No secrets or local generated artifacts staged.
- [ ] Backend tests pass.
- [ ] Frontend tests pass.
- [ ] Frontend typecheck passes.
- [ ] Backend dependency audit passes.
- [ ] Frontend dependency audit passes.
- [ ] Static security analysis passes or findings are documented.
- [ ] Alembic has one expected head.
- [ ] Production database current revision known.
- [ ] Backup/recovery confirmed if migration is required.
- [ ] Migration prechecks run.
- [ ] Production migration applied if required.
- [ ] Backend image built from intended commit SHA.
- [ ] Cloud Run revision deployed.
- [ ] Backend health and smoke tests pass.
- [ ] Frontend production build deployed to intended Firebase project.
- [ ] Auth page, workspace switching, Home, Project, Calendar, Chat smoke tests pass.
- [ ] Security smoke tests pass: HTTPS, headers, CORS, auth-required endpoint, 429,
  no debug stack traces.
- [ ] Rollback revision/release recorded.
- [ ] Deployed SHA recorded.
