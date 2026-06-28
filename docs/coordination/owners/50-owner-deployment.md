# 50-OWNER · Deployment

## Authority

Owns policy server, HTTP and ZMQ clients, request and response schemas, RTC policy, runtime interfaces, and acceleration backend protocols.

## Primary write scope

- `autovla/deployment/**`
- `autovla/acceleration/**`
- `tests/deployment/**`
- `tests/acceleration/**`
- deployment-related docs and examples
- `coordination/reports/**` for assigned reports

## Review duties

Reviews API compatibility, client/server roundtrip, RTC continuity, healthcheck behavior, backend fallback behavior, latency impact, and endpoint safety notes.

## Required report fields

Every report must include schema impact, endpoint impact, RTC impact, backend impact, latency risk, safety notes, and rollback notes.
