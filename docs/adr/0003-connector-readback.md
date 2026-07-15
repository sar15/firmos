# ADR 0003: Connector success requires read-back

Status: accepted — 14 July 2026

## Decision

OAuth success, HTTP 200 and a `connections` row do not establish a working connector. A connector capability is successful only after setup, scoped reads, mapping, idempotent queued write, provider/local read-back comparison, recovery evidence, UI status and contract tests succeed.

## Consequences

- Register tables are provider-backed projections, not independent accounting truth.
- UI capability status follows server certification state.
- Provider write errors remain visible and actionable; no silent fallback marks them successful.
