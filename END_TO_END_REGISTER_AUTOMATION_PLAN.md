# End-to-end sales and purchase register automation

## Decision

Build one evidence-to-entry pipeline for both Zoho Books and TallyPrime. A register is a generated view of posted invoices, bills, and vouchers; it is never an independently maintained spreadsheet.

Automate collection, extraction, validation, proposal, posting, read-back, register refresh, reconciliation, and exception chasing. Do **not** auto-post every document. Auto-post only when a firm's explicit policy and deterministic validations say the document is safe; otherwise create an approval task.

Portal filing remains manual.

## The customer experience

### Purchase bill

1. Client forwards a vendor PDF/image/email or uploads it to firmOS.
2. firmOS stores the original private evidence, extracts fields and line items, and shows a clear draft.
3. It finds the supplier, checks the vendor GSTIN/invoice-number/date/amount combination for duplicates, checks tax totals, and proposes an expense/stock/asset mapping from approved firm rules.
4. If every policy check passes, firmOS either posts automatically under the firm's auto-post policy or asks the assigned accountant for approval.
5. The approved bill is written to Zoho or queued to the local Tally bridge. The provider receipt is stored.
6. firmOS reads the posted record back and refreshes the purchase register and GST working.
7. If the record later appears in GSTR-2B or a bank statement, firmOS links it. If it does not, it becomes an exception, not a hidden failure.

### Sales invoice

1. firmOS observes invoices already created in Zoho/Tally and refreshes the sales register automatically.
2. If a client uploads a sales invoice created outside the books, firmOS extracts a draft, validates customer, invoice number, date, place of supply, line items, tax split, and duplicate risk.
3. It posts only after the configured policy is satisfied; otherwise the accountant sees one precise approval card.
4. firmOS reads the provider-confirmed invoice back, updates the sales register, and tracks collection/bank-match evidence.

The client should never have to choose an accounting ledger or decide CGST/SGST/IGST. The system asks only for missing business facts: supplier/customer, invoice date, place of supply, and a better image/PDF when extraction is insufficient.

## Non-negotiable control model

```
private evidence → extraction → normalized draft → deterministic checks
     → policy decision (auto-post | approval | needs client input)
     → immutable finance action → provider write → provider read-back
     → register projection → reconciliation and review queue
```

Every stage has an ID, timestamp, actor/policy reason, source hash, and provider reference. A retry uses the same idempotency key. A correction creates a reversing/adjusting action; it never silently edits historical accounting evidence.

## What we will reuse

- `documents`: evidence upload, extraction, review fields, client association.
- `finance_actions` and `finance_runs`: hash-bound proposal, approval, idempotency, execution history, Tally lease queue.
- `external_mappings`: provider ID and internal record linkage.
- `sales_register`, `purchase_register`, `gst_tax_components`: materialized reporting projections.
- Zoho OAuth client and typed `AccountingPlugin` runtime.
- Tally bridge claim/result loop and deterministic XML generation.

Do not add a workflow engine, a second queue, a generic connector framework, or a new OCR platform. The existing action engine is the outbox.

## Phase 1 — close the unsafe write path

### Goal

Make `finance_actions` the only path that can write accounting data.

### Change

1. Retire `POST /api/documents/{doc_id}/post` in `firmos-backend/api/routes/documents.py`. It currently can create contacts and choose the first expense account; that is unacceptable for unattended accounting.
2. Replace it with `POST /api/documents/{doc_id}/propose-post`.
3. The route creates a normalized draft and then a `finance_action`; it never calls Zoho/Tally directly.
4. Add a hard test: no document route may call a provider write method except through `FinanceActionEngine`.

### Policy

- Never choose “first expense account”.
- Never auto-create a supplier/customer from OCR alone.
- Never infer tax treatment merely by splitting a total in half.
- Never treat an LLM confidence score as approval.

### Acceptance

A document with all fields verified creates `PENDING_APPROVAL`; approval produces exactly one provider record; repeat requests return the same action/provider mapping.

## Phase 2 — canonical draft and deterministic validation

### Database migration

Add only these tables/columns:

- `accounting_drafts`: one normalized candidate per source document; provider, document kind, client, company, fields, line items, policy decision, source hash, lifecycle.
- `automation_rules`: firm-scoped, versioned rules such as trusted supplier/customer, allowed account/item mapping, tax treatment, amount cap, and auto-post enabled flag.
- `provider_events`: deduplicated Zoho webhook and Tally sync events with event hash and cursor.
- `sync_cursors`: per firm/provider/entity high-water mark for fallback polling.

Use unique constraints on `(firm_id, source_document_id)`, `(firm_id, provider, provider_event_id)`, and `(firm_id, provider, idempotency_key)`. Do not store another copy of source files; use the private evidence object already attached to `documents`.

### Validation order

1. File integrity and private-evidence ownership.
2. Required fields by document type.
3. Duplicate check: provider ID first; then supplier/customer GSTIN + document number + date + gross amount; flag near duplicates instead of guessing.
4. Tax reconciliation: line totals + CGST/SGST/IGST/cess must equal header totals within one paisa.
5. Master mapping: exact approved mapping only. Unknown master becomes `NEEDS_MASTER_MAPPING`.
6. Business controls: period close, backdated-entry policy, amount limit, currency, payment terms, RCM, ITC eligibility, and optional PO/GRN rule.
7. Produce the action payload and canonical payload hash.

## Phase 3 — provider adapters, one vertical slice each

### Zoho Books

Add typed operations, not generic REST passthroughs:

- `zoho.write.bill.create`
- `zoho.write.invoice.create`
- `zoho.read.bill.get`
- `zoho.read.invoice.get`
- `zoho.read.invoice.by_reference`
- `zoho.write.bill.attachment.add`
- `zoho.write.invoice.attachment.add`

Use a firmOS reference/action ID as the Zoho reference/custom unique value where Zoho supports it. First search/read by that value on retry; only then create. Attach original private evidence after a confirmed create when the provider contract allows it.

Subscribe to Zoho invoice and bill webhooks for low-latency register refresh, then retain daily cursor-based polling as the recovery path. Webhooks are hints, not proof: fetch the provider record before changing a local register.

### TallyPrime

Add exactly two typed writes after the purchase-voucher test remains stable:

- `tally.write.sales_voucher.create`
- `tally.write.purchase_voucher.create` (harden existing slice)

The local bridge should build XML/JSON from a fully validated draft, send a deterministic remote/action ID, parse Tally’s import response, then read the voucher back before marking success. Queue only one company-scoped operation at a time until live throughput proves a need for more concurrency.

Do not generate generic XML from an LLM. Export a known-good sales and purchase voucher from the customer's Tally company, compare required ledgers/GST fields, then implement that company/version contract.

## Phase 4 — automatic register refresh

### Event sources

1. Zoho invoice/bill webhook.
2. Zoho fallback poll on `last_modified_time`.
3. Tally bridge incremental voucher sync.
4. Provider write confirmation/read-back.

### Register logic

- Register rows are projections keyed by provider record ID/GUID, not manually editable rows.
- A void/cancelled provider record changes register status; it does not disappear.
- Changes are versioned in an audit trail.
- Register sync is idempotent and cursor-based; the user can still click **Sync now** for recovery.

## Phase 5 — client collection and exception automation

### Collect only what is missing

Create a secure client upload link and a structured “missing evidence” request. The request names the period, counterparty/amount/date where known, accepted file types, and due date.

Automation can send reminders only when the firm has enabled the channel and the client has consented. It stops immediately when evidence is received or an accountant marks the item not required.

### Exception routing

- Missing purchase bill from GSTR-2B: request source invoice/evidence from client; never fabricate a bill from 2B.
- Bank line without a source document: request explanation/evidence; never post an expense solely from narration.
- Unmatched sales receipt: request invoice/customer allocation; never create a sales invoice from a bank credit alone.
- Unknown master or tax treatment: assign accountant/CA, not the client.

## Phase 6 — safe automation policy

Default every firm to `approval_required`. Enable auto-post only by document direction and rule version.

### Minimum auto-post rule for a purchase bill

All conditions must be true:

- supplier has an approved mapping and is not blocked;
- supplier GSTIN, invoice number, date, total, and tax components are extracted and reconcile;
- no exact/near duplicate exists;
- mapped account/item and place of supply are approved;
- amount is under the firm-set cap;
- no RCM, asset/capitalization, foreign currency, credit note, or unusual tax flag;
- extraction is supported by original evidence;
- selected provider/company is explicit.

Everything else gets a compact approval task with the evidence, differences, and exact posting effect.

### Sales auto-post rule

Be stricter than purchase. Require an approved customer, invoice numbering policy, item/service and tax mapping, place of supply, duplicate check, and a business-approved source such as an accepted order/delivery record. A client-uploaded PDF alone defaults to approval.

## UI changes

Keep the interface to four queues, not a complex accounting console:

1. **Inbox** — received documents and extraction status.
2. **Ready to post** — drafts that pass checks; auto-post policy badge or approval button.
3. **Needs input** — one clear missing fact, with client request action.
4. **Exceptions** — duplicates, tax mismatch, GSTR-2B mismatch, bank mismatch, provider failure.

Each row answers: *what is it, why is it blocked, who owns it, what happens if I approve it?*

## Delivery order and tests

| Milestone | Deliverable | Proof before next milestone |
| --- | --- | --- |
| 1 | Remove direct document posting; action-only path | A direct document post cannot reach Zoho/Tally. |
| 2 | Purchase document → Zoho bill proposal/approval/read-back | Real Zoho sandbox bill, attachment, retry, duplicate, and void scenarios. |
| 3 | Tally purchase voucher read-back | Licensed Tally test company, repeated delivery, bridge restart, rejected XML. |
| 4 | Sales document → Zoho invoice proposal/approval/read-back | Real Zoho sandbox invoice, unique reference, tax and attachment tests. |
| 5 | Tally sales voucher | Exported company-specific fixture, live bridge receipt, read-back. |
| 6 | Webhook + cursor sync | Lost/replayed webhook and multi-page catch-up test. |
| 7 | Client evidence requests | Consent, upload, stop-reminder, assignment, and full audit test. |
| 8 | Rule-gated auto-post | Shadow mode first; measure false positives; enable by firm/rule only after CA sign-off. |

## What not to build

- No universal “write anything to Zoho/Tally” tool.
- No automatic ledger choice from an LLM or the first matching account.
- No direct posting from OCR, GSTR-2B, or bank narration.
- No public evidence URLs or shared office Tally credentials.
- No GSP/portal filing, OTP storage, or automated return submission.
- No automatic deletion/edit of a posted accounting record; issue a provider-supported reversal/correction.
- No cron-only sync with no cursor, replay handling, or manual recovery button.

## Research basis

Zoho supports typed invoice/bill APIs, provider-side references, attachments, and webhooks for invoice/bill events. TallyPrime supports structured transaction import and instructs users to check its exception reports after import. ERPNext provides the useful accounting precedent: submitted ledger history should be immutable and cancellation should use reverse entries rather than deletion.
