# firmOS V1 execution contract

## Product boundary

V1 accepts manual uploads of accounting and tax evidence. It automates extraction, validation, drafts, mapping assistance, approved accounting posts, read-back verification, register projections, reconciliation, workpapers and manual filing packs.

Government-portal login, CAPTCHA, OTP/EVC/DSC completion, tax payment and statutory submission remain manual in V1. Connector writes are never initiated by an LLM tool or an approval HTTP request.

## Implementation rules

- Work in the Connector-First Execution Blueprint order; do not build later workflows on uncertified connector behavior.
- Trace callers, tests and migrations before changing code. Reuse an existing seam before creating a new abstraction.
- Keep production source files under 300 lines. Split by responsibility, never by arbitrary line count.
- Money is integer paise at boundaries; never introduce `float` conversion.
- A provider write requires durable approval, idempotency, queued execution, read-back verification, evidence and audit history.
- A visible capability must be backed by an enabled server capability; no mock or silent fallback is a successful outcome.
- Applied migrations are immutable. Correct them with a new forward migration.

## Repository phase invariant

The repository map is the sole entry point for selecting an implementation seam. If a task would create a second auth, money, queue, connector, document, register or workflow path, stop and update the approved path instead.
