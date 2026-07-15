# Repository map

Last verified: 14 July 2026. This is a responsibility map, not a copy of the directory tree.

## Approved implementation seams

| Concern | Owner | Approved code path | Source of truth | Replacement path |
| --- | --- | --- | --- | --- |
| HTTP API | Platform | `firmos-backend/api/main.py` and `firmos-backend/api/routes/` | PostgreSQL/Supabase through backend dependencies | Keep routes thin; move domain logic in place to `firmos-backend/core/` or its owning domain. |
| Authentication and tenant context | Platform/security | `firmos-backend/api/deps.py`, `firmos-backend/core/security.py` | Validated JWT claims and the `firms` table | Refactor in place into `firmos-backend/core/`; do not add a second browser-supplied tenant path. Current preview identity is not production auth. |
| Settings | Platform | `firmos-backend/core/config.py` | Process environment | Keep one cached `get_settings()` factory; the `settings` proxy is compatibility-only. |
| Money conversion | Accounting platform | `firmos-backend/engines/gst_components.py` | Integer paise in database and API models | Use `paise()` for new provider-value conversion until a later task moves it into `firmos-backend/core/`. Do not add local converters. |
| Database and RLS context | Platform/security | `firmos-backend/core/database.py`, `firmos-backend/api/deps.py` | Supabase migrations under `supabase/migrations/` | Refactor the existing transaction dependency; never infer schema from a route. |
| Finance jobs and write boundary | Accounting platform | `firmos-backend/core/finance_actions/engine.py` | `finance_actions`, `finance_runs`, `external_mappings` | Make this persistent-only in place; provider writes must not bypass it. |
| Connector capability contracts | Connector team | `firmos-backend/connectors/accounting.py` | Connector capability declarations and `connections` | Extend the existing connector package; do not add route-specific provider clients. |
| Zoho Books | Connector team | `firmos-backend/connectors/zoho_books/` | Zoho provider read-back plus `connections`, `external_mappings` | Harden this package in place with pooled transport, mappings and verifier. |
| Tally Prime | Connector team | `firmos-bridge/` and `apps/firmos-agent/` | Local Tally read-back plus `tally_*` tables and finance actions | Move bridge behavior gradually into `apps/firmos-agent/`; retain legacy bridge only for compatibility tests. |
| Documents and drafts | Document automation | `firmos-backend/api/routes/documents.py`, `firmos-backend/extraction/` | `documents`, `accounting_drafts`, private storage | Split storage, extraction, review and posting responsibilities without a parallel upload path. |
| Purchase and sales registers | Accounting platform | `firmos-backend/api/routes/registers.py` | `purchase_register`, `sales_register` as provider-backed projections | Keep reads here; make sync queued and verified before treating rows as current. |
| Reconciliation | Reconciliation | `firmos-backend/api/routes/reconciliation.py`, `firmos-backend/engines/` | `reconciliation_matches`, `gstr2b_uploads`, bank evidence tables | Version matching logic in place; preserve import evidence. |
| Workflows and agent planning | Automation | `firmos-backend/workflows/graphs.py` | Durable action/job records, not graph memory | Workflows orchestrate only; provider SDK calls stay in connector/job code. |
| Product UI | Web product | `apps/web/src/features/`, `apps/web/src/app/` | FastAPI OpenAPI contract and backend responses | Keep feature API files until generated contracts replace them. |

## Data ownership

| Data | Owning table(s) | Rule |
| --- | --- | --- |
| Firm and connector installation | `firms`, `connections`, `oauth_connection_attempts` | A connection row alone never proves connector readiness. |
| Evidence and extracted facts | `documents`, private object storage, `accounting_drafts` | Original evidence remains immutable; drafts are revisable. |
| Approved external mutations | `finance_actions`, `finance_runs`, `external_mappings`, `audit_log` | Idempotency, execution status and provider identifiers live here. |
| Accounting projections | `purchase_register`, `sales_register` | Projections are not an independent accounting truth; refresh from verified provider reads. |
| Tally synchronisation | `tally_ledgers`, `tally_vouchers`, `tally_sync_logs` | Device and provider confirmation are required before success. |
| Reconciliation evidence | `gstr2b_uploads`, `reconciliation_matches`, `zoho_bank_match_cases`, `zoho_bank_match_candidates` | Preserve source upload and match evidence together. |
| Bank evidence | `bank_statements`, `bank_transactions` | Treat documents and statements as private financial evidence. |

## Deliberately non-authoritative paths

- `graphify-out/`, `all_code.txt`, `all_docs.txt`, `curl_out*.json` and root scratch files are generated or temporary artifacts.
- `firmos-backend/scripts/live/` contains operator-run probes, never unit tests.
- Root-level historical plans may inform decisions but do not override `docs/current/` or accepted ADRs.

Every code path named above exists in this revision. Planned destinations are expressed as existing owning directories so this map never pretends an uncreated module already exists.
