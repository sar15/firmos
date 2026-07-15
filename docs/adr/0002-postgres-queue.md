# ADR 0002: PostgreSQL-backed execution queue

Status: accepted — 14 July 2026

## Decision

Use persistent PostgreSQL records for finance actions, attempts, leases, idempotency and recovery. The `finance_actions` state machine is the single write boundary; Tally workers pull approved work and Zoho work is executed outside approval requests.

## Consequences

- In-memory action state is test-only and must be removed from production paths.
- Every execution has a correlation identifier, durable attempt record and typed failure outcome.
- Introducing a separate broker requires a measured operational need and a new ADR.
