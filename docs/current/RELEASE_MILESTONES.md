# Release milestones and evidence boundary

Updated: 15 July 2026. Sections 22 and 23 of the execution blueprint are intentionally out of scope.

`Implemented` means the repository path and local certification evidence exist. `Pilot required` means the code must remain behind its default-off write gates until installation-specific evidence is approved. A test double is never pilot evidence.

| Milestone | Repository state | Release state | Remaining evidence |
| --- | --- | --- | --- |
| A — Safe engineering baseline | Implemented and locally verified | Ready for deployment configuration review | Production secrets, domains, backup/restore drill and environment-specific RLS check |
| B — Connector platform internal | Queue, worker, attempts, capabilities, test kit and write gates implemented | Local L2 boundary | Internal deployment observation; production writes remain off |
| C — Zoho purchase pilot | Paginated reads, mapping, immutable queued purchase bill, read-back and verification implemented | Pilot required | Zoho test organization L3, internal L4 and installation-specific L5 |
| D — Tally read pilot | Signed paired agent, company GUID mapping, heartbeat, diagnostics and verified read sync implemented | Physical pilot required | Supported Windows/Tally version evidence |
| E — Tally purchase pilot | Exactly-once logical action, strict import parsing, local read-back and restart recovery implemented | Physical pilot required | Real-company write/read-back and restart exercise |
| F — Purchase automation beta | Upload, evidence review, immutable posting action, verified register projection and exception flow implemented | Depends on C or E | Real CA completes the loop without developer help |
| G — Reconciliation beta | GSTR-2B/IMS and bank reconciliation workflows implemented | Controlled beta required | Real datasets, balancing evidence and CA sign-off |
| H — Compliance preparation | Sales register, manual GST pack and selected ITR draft workflows implemented | Controlled beta required | Current domain-rule review and CA sign-off; filing remains manual |
| I — Agent operating layer | Typed plans, financial diffs, exception inbox and truthful run timeline implemented | Local evaluation ready | Authenticated browser evaluation with pilot data |

## Trustworthy-loop evidence

| Loop stage | Durable seam |
| --- | --- |
| Source evidence | Private documents, extraction runs and source IDs |
| Deterministic draft | Versioned accounting draft and integer-paise validators |
| Reviewed immutable action | Payload hash, explicit permission and approval identity |
| Durable execution | Finance action, queue job, lease and append-only attempts |
| Real provider object | Provider/local identifier stored only after a real response |
| Read-back verification | Field-level verification with mismatch/review state |
| Verified projection | Purchase/register projection after successful verification |
| Audit evidence | Correlation ID, attempts, action history and evidence lineage |

## Definition-of-done interpretation

A feature may be called fully functional only after every applicable blueprint item is evidenced for the exact provider version and installation. Local completion establishes implementation and simulator confidence, not real-provider success. In particular, no milestone requiring L3-L5 evidence or real-CA use is complete until that external evidence exists.

The release owner must attach: test identity and scope, capability key, provider version, correlation IDs, approved payload hash, provider object ID, read-back result, failure-recovery exercise, kill-switch exercise, monitoring snapshot, runbook version and accountable sign-off.

## Current blockers that must remain visible

- Zoho and Tally production writes are default-off and unavailable without installation-specific L5 certification.
- Tally has no completed physical Windows/Tally certification record, so its supported write allowlist remains empty.
- Government submission, OTP/EVC/DSC, CAPTCHA and payment remain manual V1 boundaries.
- The web dependency audit currently reports a moderate transitive `postcss` advisory through Next.js; no non-breaking upstream resolution is available in the installed range. High/critical audits remain release-blocking.
