# Operator runbook v1.0.0

Effective: 15 July 2026. This runbook governs the connector-first source-to-verified-result loop.

## Before enabling a pilot

1. Confirm the exact installation, provider version and capability has an approved L5 certification record.
2. Confirm the user, firm, client and provider organization/company binding.
3. Verify private storage, RLS, backups, worker heartbeat, connector probe and alert delivery.
4. Confirm the global write flag is off, then enable only the pilot installation and capability.
5. Submit a reversible approved test action and retain its correlation ID.
6. Confirm provider/local read-back, field verification, projection and audit evidence.
7. Exercise the narrow capability kill switch and confirm readiness becomes unavailable.

## Normal operator flow

Follow one action from evidence to verified projection. The UI must show source IDs, immutable payload hash, approval identity, queue/run state, correlation ID, provider reference, verification result and recovery action. Treat any missing stage as incomplete, never as success.

## Recovery matrix

| State | Operator action |
| --- | --- |
| `AUTH_EXPIRED` | Disable the affected capability, reconnect credentials and retry the durable job |
| `NEEDS_INPUT` | Supply missing evidence or approve the required mapping; do not edit an approved payload |
| `FAILED` before provider call | Correct the typed input and create a new proposal/version |
| Timeout or lost response | Do not post manually; recover by idempotency/reference lookup and mandatory read-back |
| `PROVIDER_ACCEPTED` | Wait for verifier; do not interpret acceptance as completion |
| `NEEDS_REVIEW` or mismatch | Compare approved fields with read-back, preserve evidence and escalate to an authorized reviewer |
| `DEAD_LETTER` | Inspect append-only attempts, correct the recoverable cause, then use the explicit retry path |
| Tally device offline/restarted | Keep writes disabled until heartbeat, company GUID and sync completeness recover |
| Duplicate delivery | Confirm the same logical action/provider object; never create a replacement write |

## Emergency stop

Disable the narrowest applicable capability override first. If scope is uncertain, set the global provider-write environment switch false and restart workers. For Tally, also turn off writes in the paired local agent. Do not delete jobs, attempts, audit rows, provider references or certification evidence.

## Incident evidence

Record UTC time, operator, firm/client, installation, capability, correlation and action IDs, payload hash, attempt sequence, provider reference, read-back, projection state, redacted logs, kill switch used and recovery decision. Never copy access tokens, document text or financial payloads into an incident channel.

## Rollback rules

- Web/API: deploy the last reviewed artifact when schema compatibility is preserved.
- Worker/scheduler: stop consumption before rollback; retain leases and resume through durable recovery.
- Database: never revert an applied migration. Create a reviewed forward fix and verify both fresh and upgrade paths.
- Tally agent: use only signed release rollback artifacts supported by its installer policy.

## Re-enable rule

Re-enable only after the cause is understood, the exact recovery test passes, monitoring is healthy, certification remains valid and a second authorized operator reviews the evidence. If provider behavior or version changed, demote certification and repeat the required level.
