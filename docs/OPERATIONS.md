# Operations

## Health

`GET /health` verifies the process is alive and returns non-sensitive service metadata.
It is not a deep database readiness check.

## Logs

Backend logs are structured by default. Every request receives an `X-Request-ID`; use it
to correlate HTTP logs with agent/tool/LLM events.

Inspect Cloud Run logs after deploy for:

- startup exceptions;
- missing config;
- database connectivity failures;
- migration mismatch;
- 5xx responses;
- unexpected auth failures;
- rate limit spikes.

## Common Failure Modes

- Database revision behind app code: stop deploy and run the migration gate.
- CORS failure: verify `CORS_ALLOWED_ORIGINS` and Firebase rewrite behavior.
- Upload failure: verify `GCS_BUCKET_NAME` and runtime service account permissions.
- Email failure: verify SES region/sender and AWS/IAM credentials.
- Agent state loss: verify `DATABASE_URL` and Postgres checkpointer connectivity.

## Configuration Changes

Apply production secrets through the approved secret mechanism. Non-secret settings may
be updated as Cloud Run environment variables. Avoid putting private backend values in
frontend Vite variables.

## Observability

Use Cloud Run logs/metrics for 5xx, latency, instance startup, and rate-limit behavior.
The app records LLM call rows for cost/latency observability.
