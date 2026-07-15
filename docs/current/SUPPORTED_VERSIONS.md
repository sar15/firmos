# Supported-version matrix

Only items with a repository baseline are listed as supported. “Not certified” means no V1 compatibility promise.

| Area | Current baseline | Status | Evidence |
| --- | --- | --- | --- |
| Python backend | Python 3.12+ | Supported development baseline | `firmos-backend/pyproject.toml` |
| Web runtime | Node.js 20 Alpine | Supported build baseline | `apps/web/Dockerfile` |
| Desktop agent | Tauri/Rust dependencies locked in `apps/firmos-agent/` | Build baseline only | Agent lockfiles and Cargo manifest |
| Local database | `supabase/postgres:15.8.1.145` | Local development baseline | `firmos-backend/docker-compose.yml` |
| Hosted Supabase | PostgreSQL/Supabase service matching migration features | Not release-certified | Requires fresh/upgrade CI and RLS certification |
| Zoho Books | API v3 | Code integration baseline, not write-certified | `connectors/zoho_books/client.py` |
| TallyPrime | No exact `$$Version` value certified | Read/write blocked for release claims | `connectors/tally/versions.py`; TA-026 evidence required |
| Windows | Windows 10/11 x64 build target, no signed installer certified | Build target only | Tauri NSIS/MSI workflow; physical install test pending |
| Document evidence | PDF and image uploads | Supported ingestion input baseline | `api/routes/documents.py` |
| Bank statements | CSV | Supported parser baseline | `api/routes/bank_statements.py` |
| GSTR-2B/IMS, AIS/TIS/26AS/Form 16 evidence | Manual upload only | Workflow scope, format certification pending | V1 execution contract |

Update this matrix only with a reproducible test record. Do not turn an implementation detail into a support claim.

## Tally protocol matrix

The runtime reports the exact value returned by Tally `$$Version`. An unlisted value is deliberately read/write-ineligible for production certification.

| Exact Tally version | XML read | XML purchase write | JSON read/write | Certification |
| --- | --- | --- | --- | --- |
| _None yet_ | Blocked for release claim | Blocked | Not implemented | Run TA-026 against a licensed installation and record the evidence before adding a row |

Known limitations: the local connection is XML over Tally's loopback HTTP port; only approved purchase-voucher creation is in write scope; Educational mode, missing company GUID, incomplete sync/mapping, disabled local write permission, and unlisted versions block writes. JSON and portal automation are not claimed.
