# Security Verification

| Control area | Threat | Implementation | Evidence | Status | Remaining risk |
|---|---|---|---|---|---|
| Authentication | Unauthenticated API access | `@jwt_required()` on protected routes | `pytest`, route audit | PASS | Public auth endpoints remain intentionally unauthenticated |
| Workspace isolation | IDOR/cross-tenant access | `user_can_access_workspace`, object workspace checks | `tests/test_authz.py`, agent auth tests | PASS | Continue adding tests for new route groups |
| Agent tool identity | Prompt/tool argument spoofing | `ExecutionContext` is authoritative | execution context tests | PASS | External MCP configuration must supply correct trusted context |
| Rate limiting | Credential stuffing/API abuse | DB-backed fixed-window limiter | `test_auth_rate_limit_returns_429_with_retry_after` | PASS | Policy values may need tuning under real traffic |
| CORS | Cross-origin credential abuse | Explicit origin list config | config review | PASS | Must keep production origins explicit |
| CSRF | Browser-forged mutation | Bearer tokens in Authorization header | architecture review | PARTIAL | localStorage token theft remains XSS-sensitive |
| XSS | Untrusted HTML execution | React escaping, limited markdown renderer | grep for dangerous APIs | PASS | Continue reviewing any rich preview feature |
| SQL injection | Raw SQL injection | SQLAlchemy ORM; migration SQL is static | grep for raw SQL | PASS | Review any future dynamic SQL |
| SSRF | Metadata/private network fetch | live research disabled by default; URL validation | SSRF regression tests, Bandit | PASS | DNS rebinding protections are bounded to pre-fetch resolution |
| File upload | Path traversal/unsafe upload | secure filename, extension/size checks, workspace auth | upload security test | PASS | MIME validation is extension-based, not deep content scanning |
| Security headers | Clickjacking/MIME/referrer leaks | Flask after-request headers | header regression test | PASS | Firebase static headers should be reviewed on deploy |
| Dependencies | Known vulnerable packages | npm audit, pip-audit | both audits clean | PASS | Keep Dependabot/CI audits enabled |
| Secrets | Secret leakage | `.gitignore`, local `.env` untracked | grep and git tracked-file check | PARTIAL | Real local `.env` exists; do not stage it |
| Error handling | Stack trace exposure | global exception handler returns generic JSON | tests plus code review | PASS | Some route-specific errors still return plain strings |
| Time handling | Timezone drift | UTC intended | test warnings | PARTIAL | Many `datetime.utcnow()` warnings remain |
