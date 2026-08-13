# Security

This document describes verified controls and known remaining risks. It is not a
certification claim.

## Authentication

- JWT bearer tokens protect authenticated APIs.
- Passwords are hashed with Werkzeug password hashing.
- Email verification and password reset tokens are stored server-side.
- Verification OTP generation uses `secrets`, not pseudo-random generation.
- OAuth uses Authlib provider clients when configured.

## Authorization And Workspace Isolation

Protected resources must check workspace membership or ownership server-side. The
shared baseline is `app/core/authz.py`.

Covered by tests:

- unauthenticated protected endpoint behavior;
- cross-workspace task mutation rejection;
- workspace member list isolation;
- user workspace list enumeration prevention;
- agent context cross-workspace mutation rejection;
- prompt-injection/tool identity isolation tests.

## Rate Limiting

`app/core/rate_limit.py` implements database-backed fixed-window limits. This works
across multiple Cloud Run instances without relying on local process memory.

Policies:

- auth-sensitive endpoints: strict;
- chat/planning/scheduling AI endpoints: moderate;
- search: moderate-high;
- mutations: bounded;
- reads: higher.

429 responses include `Retry-After`.

## CORS And CSRF

Production CORS uses explicit configured origins. Authenticated mutations use bearer
tokens in the `Authorization` header rather than cookies, so conventional browser CSRF
risk differs from cookie-auth apps. Do not enable wildcard CORS for authenticated APIs.

## Headers

The backend applies API-safe headers:

- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `X-Frame-Options: DENY`
- `Permissions-Policy`
- restrictive API `Content-Security-Policy`
- HSTS when the request is HTTPS

Firebase Hosting headers should also be kept restrictive for static frontend assets.

## Input And Upload Validation

- Request body size is bounded by `MAX_CONTENT_LENGTH`.
- Document uploads validate workspace access, filename, extension, upload size, and tag
  bounds before writing to storage.

## SSRF

Live research fetching is disabled by default. When enabled, research URL fetches only
allow HTTP/HTTPS and reject localhost, metadata hostnames, private IPs, loopback,
link-local, multicast, reserved, and unspecified addresses before `urlopen`.

## LLM And Agent Boundaries

External research/document/user content is treated as data, not instructions. LLM output
cannot override `ExecutionContext`, user ID, workspace ID, tool authorization, or risk
policy.

## Secrets

Do not commit `.env`, service account JSON, tokens, private keys, or database URLs with
passwords. Production secrets must come from approved secret/config mechanisms. Any Vite
variable included in the frontend bundle is public.

## Verification Commands

```bash
cd backend && .venv/bin/pip-audit -r requirements.txt
cd backend && .venv/bin/bandit -r app -x '*/__pycache__/*'
cd frontend && npm audit
```

Remaining risk: broad UTC cleanup remains because many models/services still use
`datetime.utcnow()`. Tests pass, but the warning volume should be reduced before relying
on Python versions that remove the API.
