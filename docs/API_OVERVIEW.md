# API Overview

The backend exposes REST APIs under `/api/v1` and `/api/v2`, plus limited protocol
endpoints for health, A2A, and MCP-adjacent operation.

## Auth

`/api/v1/auth/*`

- public: register, login, forgot/reset password, OAuth redirects;
- authenticated: current user, profile update, email verification/resend.

## Workspaces

`/api/v1/workspaces/*`, `/api/v1/users/<id>/workspaces`

All workspace data access must be scoped to the authenticated user. Cross-user
workspace enumeration is forbidden.

## Projects And Tasks

`/api/v1/projects/*`, `/api/v1/tasks/*`

Object IDs must be checked through workspace membership. Mutation routes return 403
when the user can authenticate but cannot access the owning workspace.

## Calendar And Scheduling

`/api/v1/workspaces/<id>/events`, `/api/v1/schedule-proposals/*`

Calendar events and schedule proposals are workspace-scoped. Applying a schedule
proposal goes through trusted execution context.

## Chat And Agents

`/api/v1/chat/*`, `/api/v1/agents/*`, `/api/v1/plans/*`

Chat message sending streams SSE events. Agent-generated tool arguments remain
untrusted; the server-side execution context controls identity and workspace.

## Documents

`/api/v1/documents`, `/api/v1/workspaces/<id>/documents`

Uploads are multipart, authenticated, workspace-scoped, size-limited, and extension
restricted.

## Organizations, Team, Billing, Modules

`/api/v2/orgs/*`, `/api/v2/billing/*`, `/api/v2/modules/*`

Organization/team routes use membership and role checks. Platform-admin billing routes
require explicit platform admin status.

## Error Model

Current APIs return JSON objects with an `error` string for failures. Common status
codes:

- 400 invalid input;
- 401 unauthenticated;
- 403 authenticated but unauthorized;
- 404 not found or inaccessible resource;
- 409 conflict;
- 413 request/upload too large;
- 429 rate limited;
- 500 internal error.
