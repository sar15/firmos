# firmOS feature guide

firmOS is a review-first workspace for CA firms, accountants, and tax teams. It reads accounting evidence, explains exceptions, prepares working papers, and writes to an accounting system only through a typed, approval-gated action. GST portal filing is manual.

## Start here

1. Open **Connectors** and complete the readiness checklist.
2. Connect Zoho Books, or install the Tally bridge on the office machine that has TallyPrime and the intended company open.
3. Open **Clients**, select a client, and work with one return period at a time.
4. Sync registers before reconciliation or GST preparation.

## Client workspace

| Where | Use it for | How it works |
| --- | --- | --- |
| **Clients** | Find and open a taxpayer/client | Search the client list, then use the client workspace as the scope for registers and reconciliation. |
| **Client profile** | See client context and work items | All evidence, actions, and reviews are firm- and client-scoped. Do not use a generic test client. |
| **Sales Register** | Period sales evidence | Choose a GST period and press **Sync**. firmOS reads the selected Zoho period, stores a local review projection, and shows invoice totals and tax totals. |
| **Purchase Register** | Period purchase evidence | Choose the same period and press **Sync**. firmOS reads Zoho bills, retains supplier/bill evidence, and stores GST components when Zoho supplies them. |

## Zoho Books

| Capability | Where to use it | What happens |
| --- | --- | --- |
| OAuth connection | **Connectors → Zoho Books** | You approve access in Zoho and select the organization. Tokens remain encrypted in firmOS. |
| Read sales, bills, contacts, and accounts | Registers and agent tools | firmOS reads only the selected period or requested resource; register sync paginates so it does not silently stop at a default page size. |
| Create a purchase bill | **Agent** proposal → approval card | The agent creates a typed bill proposal. Review all details and approve the payload hash. Only then is the bill sent to Zoho. |
| Bank candidate review | Bank-reconciliation workflow/API | firmOS asks Zoho for candidates for one uncategorized line, stores the returned evidence, and lets a reviewer choose from those candidates only. |
| Match a bank line | Approval card after candidate review | The approved match is written back to Zoho. firmOS does not invent a candidate or execute an unapproved match. |

## TallyPrime

| Capability | Where to use it | What happens |
| --- | --- | --- |
| Connect Tally | **Connectors → TallyPrime** | Install the firmOS Bridge on the office computer. Keep the intended licensed Tally company open. The bridge is local; Tally is not exposed to the internet. |
| Read ledgers and vouchers | Bridge sync | The bridge pushes canonical ledger and voucher data to firmOS with firm/company scoping and idempotency. |
| Create a purchase voucher | Agent proposal → approval → bridge queue | An approved action is queued. One registered bridge leases it, builds Tally XML, sends it to TallyPrime, and reports the provider receipt. |
| Other Tally writes | Not yet enabled | Sales vouchers, payment vouchers, masters, and arbitrary Tally operations are deliberately not advertised as working until each has a typed payload, bridge receipt handling, and licensed-company test. |

## Bank reconciliation

1. Open **Reconciliation** and choose the client and period.
2. Upload a CSV, XLS/XLSX, or PDF bank statement. firmOS parses transactions and checks running balances. Scanned PDFs can escalate to OCR when configured.
3. Review exact, suggested, and unmatched lines. Do not auto-accept an unexplained suggested match.
4. For Zoho-connected bank lines, use Zoho’s own candidate list. Select a candidate, review the proposed match, and approve it.
5. Open supporting evidence through the statement’s signed download link. It expires after five minutes.

## GSTR-2B and GSTR-3B working

1. Download GSTR-2B JSON manually from the GST portal.
2. In **Reconciliation**, select **GSTR-2B ↔ Purchases** and upload that JSON for the exact period.
3. Resolve suggested and unmatched purchase evidence. Each exception retains its source/target amounts for review.
4. Sync Zoho sales and purchases. firmOS records taxable value, CGST, SGST, IGST, and cess separately when the provider source proves the split.
5. Review every purchase component and explicitly mark ITC eligibility.
6. Open the **GST/Compliance** working pack. It contains sales register, purchase register, 2B mismatch report, component completeness, 3B working, and review checklist.

The 3B tables remain blocked if tax components are unknown, ITC is undecided, or 2B exceptions remain. This is intentional. A CA reviews the result and files manually on the GST portal.

## Documents and review workflow

| Where | Use it for | How it works |
| --- | --- | --- |
| **Documents** | Upload bills and supporting evidence | Upload a document, review extracted fields, correct a field, and choose post, reject, or needs-info. |
| **Decisions** | Assign/review a question or exception | Open the decision context, draft a response, and approve it when ready. |
| **Notifications** | Follow assigned work and changes | Mark a single notification or all notifications as read. |
| **Audit** | Verify what happened | See the action lifecycle, approver, payload hash, provider reference, and timing. It is the source of truth for an external write. |

## Agent workspace

1. Open **Agent**.
2. Select a real client and month.
3. Ask for sales/purchase totals, GSTR-2B status, exceptions, or the next review action.
4. For an accounting write, provide the required business details. The agent returns a proposal, not a fake completion message.
5. Check the client, provider, amount, payload hash, and target. Approve only if all are correct.
6. Watch the lifecycle: `PENDING_APPROVAL` → provider-confirmed success for Zoho, or `QUEUED` → bridge confirmation for Tally.

## Setup and release readiness

Open **Connectors**. The readiness checklist checks database reachability, JWT mode, mock disablement, Zoho organization status, Tally bridge activity, and the manual GST boundary.

For production, use JWT auth and strict-no-mock mode. The app refuses to start in production mode with development authentication.

## Important limits

- GST portal filing, OTP handling, and GSP submission are not part of firmOS.
- Zoho/Tally are not universal plugins yet. Only declared, tested operations can write.
- A manual CA review is mandatory before filing GSTR-3B.
- A private evidence link is intentionally temporary; re-open it from the statement list if it expires.
