# Connector certification and release runbook

This runbook is the release authority for every provider, provider version, installation, and capability. Certification never transfers between versions, installations, organizations, or capabilities.

## Levels

| Level | Required evidence |
| --- | --- |
| L0 | The implementation exists behind a disabled production-write gate. |
| L1 | Unit and connector contract tests pass. |
| L2 | Provider simulator fault tests pass, including throttling, expired auth, timeouts, partial pages, duplicate recovery, ambiguous outcomes, and read-back mismatches. |
| L3 | The complete flow passes in a provider sandbox or dedicated test company. Evidence includes correlation IDs, object IDs, pagination totals, and read-back results. |
| L4 | A controlled internal real-account test passes with approved, reversible test data and an operator observing recovery. |
| L5 | A pilot installation passes the release checklist and its evidence is approved by an accountable operator. |

Production UI and workers may report a write capability `AVAILABLE` only when its exact installation, provider version, and capability have an L5 record. All lower levels must remain blocked.

## Current evidence boundary

- Zoho Books API v3: local implementation, contract tests, and fault simulation can establish at most L2. L3 requires a connected Zoho test organization; L4 requires an approved internal organization; L5 requires a pilot installation. Until those runs occur, Zoho writes remain blocked even though the code is release-ready.
- TallyPrime: local implementation and simulator work can establish L1/L2. Windows service, supported-version, real-company read/write/read-back, updater, and pilot evidence require a physical Windows/Tally environment and remain deferred.

Never promote a level from a written claim or a test from another installation.

## Release checklist

Every item must have linked evidence before L5:

- real user identity, tenant, installation, and organization/company binding;
- credential rotation, revocation, and disconnect verified;
- exact OAuth/device capability reporting, with missing scope blocked;
- complete paginated reads and explicit completeness counts;
- resumable partial sync without duplicate canonical objects;
- stable provider object identities and explicit client mapping;
- deterministic integer money and normalized provider dates;
- immutable approval before mutation;
- durable job and attempt history;
- stable logical idempotency key;
- preflight and post-timeout ambiguous-outcome recovery;
- mandatory read-back and durable mismatch review state;
- redacted audit evidence with correlation IDs;
- global, provider, firm, client, and capability kill switches;
- operator recovery for failed reads and review-only recovery for uncertain writes;
- sandbox, simulator, and fault-test evidence;
- this versioned runbook reviewed for the released provider version.

## Promotion procedure

1. Select one installation, provider version, and capability.
2. Run the tests required for the target level and retain only redacted evidence.
3. Confirm every lower level is already evidenced for the same scope.
4. For L3-L5, record test organization/company identity, timestamp, operator, correlation IDs, expected result, provider IDs, read-back result, recovery exercise, and checklist outcome.
5. Have a second authorized operator review L4/L5 evidence.
6. Insert or update the server-owned certification record. Client applications must never write certification rows.
7. Re-read `/api/capabilities` and confirm the exact state. Exercise the kill switch before enabling a pilot.

Required certification fields are `firm_id`, `installation_id`, `provider`, `provider_version`, `capability_key`, `certification_version`, `certification_level`, `evidence`, and `certified_by`.

## Rollback and incident rule

Disable the narrowest applicable kill switch immediately when identity, scope, mapping, idempotency, provider behavior, or read-back truth is uncertain. Do not retry an uncertain write manually. Preserve the job, attempt, audit, and provider IDs; move it to review; recover by exact reference and mandatory read-back. Demote or remove the affected certification before re-enabling production writes.
