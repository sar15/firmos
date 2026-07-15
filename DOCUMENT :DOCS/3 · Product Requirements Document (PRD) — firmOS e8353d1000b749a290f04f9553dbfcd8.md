# 3 · Product Requirements Document (PRD) — firmOS

## firmOS · Product Requirements Document

**Version 1.0 · June 2026 · Execution-ready**

---

## 1. Users & Personas

### Persona 1: The Practicing CA — Primary User

**Profile:** Chartered Accountant, 2–15 years experience. Manages 30–150 clients across GST, income tax, TDS, audit, ROC. Team of 2–15 people (article clerks, accountants). Currently uses Tally + Excel + ClearTax + 6 different portal logins. Works 60+ hours/week.

**Day in the life today:** Logs into GSTN portal for Client 1. Downloads 2B. Opens Excel. Pastes data. Opens Tally. Exports purchase register. Pastes into Excel. Matches manually. Finds 3 mismatches. Calls the client. Repeats for Client 2. It's 7 PM and there are 12 clients left.

**What they want from firmOS:**

- Complete monthly compliance cycle for 40 clients in 2 days, not 2 weeks
- Never miss a deadline because of portal downtime or workload
- Be able to take on 50 more clients without hiring 5 more staff
- Prove to clients that their CA is on top of things with instant status updates

**What they fear:**

- Getting a client a penalty due to a missed filing
- A system making an error they didn't catch
- Losing control over their professional responsibility
- Data of their clients leaking

**Quote:** *"I didn't study for 5 years to copy-paste between Tally and a government website."*

---

### Persona 2: The Finance Manager / Controller — Secondary User

**Profile:** Works inside a business (not a CA firm). Manages AP/AR, vendor payments, payroll, GST compliance for their company. Hires a CA firm externally for audit and major filings. 5–15 years experience.

**Pain:** Coordinating between accounting software, the CA, and multiple portals. Manually processing 200+ vendor bills per month. Chasing the CA for filing confirmations. Month-end close takes 5 days.

**What they want:**

- Vendor bills processed automatically from WhatsApp
- Bank reconciliation done daily, not monthly
- Monthly GST done without manual portal work
- One place to see all compliance status

---

### Persona 3: The Individual Taxpayer — Tertiary User

**Profile:** Salaried employee or small business owner. Files ITR once a year. Doesn't understand Form 16, AIS, capital gains. Currently pays a CA ₹2,000–5,000/year for basic ITR filing.

**Pain:** Not understanding their own tax situation. Getting a notice and panicking. Not knowing if they're paying too much tax.

**What they want:** Tell firmOS their situation → ITR filed → explanation in plain language.

---

## 2. Core Jobs-to-be-Done

| Job Statement | Frequency | Current time | Target time |
| --- | --- | --- | --- |
| File GSTR-3B for one client | Monthly | 2–3 hours | 5 minutes |
| File GSTR-1 for one client | Monthly | 1–2 hours | 3 minutes |
| File ITR for one client | Annual | 3–8 hours | 10 minutes |
| Reconcile bank statement | Monthly | 2–4 hours | Automated + 5 min |
| Process vendor bill | Per bill | 10–15 min | 90 seconds |
| File TDS return (26Q) | Quarterly | 2–3 hours | 10 minutes |
| Process payroll for one company | Monthly | 1–2 hours | 5 minutes |
| File MGT-7 annual return | Annual | 4–6 hours | 30 minutes |
| Draft Tax Audit 3CD | Annual | 3–5 days | 2–3 hours (CA review only) |

---

## 3. User Journeys

### Journey 1: CA Onboards a New Client

1. CA creates client profile in firmOS: name, PAN, GSTIN(s), accounting software credentials
2. firmOS fetches filing history from GSTN and IT Portal (past 12 months)
3. firmOS generates compliance calendar (all upcoming deadlines for all return types)
4. firmOS shows compliance health: what's current, what's pending, what's overdue
5. CA sees the complete picture of a new client in **60 seconds**

### Journey 2: Monthly GSTR-3B Cycle for 40 Clients

1. **Day 12 of month:** firmOS auto-triggers GSTR-3B preparation for all active GST clients
2. **Agent runs (5–10 min per client):** fetches 2B, reads books, matches, computes, creates draft
3. **CA inbox notification:** "28 GSTR-3B drafts ready — 3 need attention (ITC issues)"
4. **CA reviews high-attention items first:** sees mismatch detail, approves or adjusts
5. **CA bulk-approves clean returns:** 25 returns with no exceptions approved in < 10 minutes
6. **Agent files:** submits all 28 to GSTN, stores ARNs, marks calendar complete
7. **CA confirmation:** "28 returns filed. Total payable: ₹12.4L. Challans generated."
8. **Entire process:** 45 minutes for 40 clients. Previously: 80 hours.

### Journey 3: Vendor Bill Processing via WhatsApp

1. Client photos a vendor bill and sends on WhatsApp to their CA's firmOS number
2. firmOS bot acknowledges: "Got it. Processing your bill..."
3. Gemini Vision extracts: vendor name, GSTIN, invoice number, date, taxable, CGST, SGST, total
4. Validation: GSTIN checksum check, arithmetic verification (taxable + CGST + SGST = total ±₹1), duplicate check against existing entries
5. Action proposal created: "Approve vendor bill: Shree Traders ₹18,450 dated 15 Jun"
6. CA approves on firmOS inbox or replies "1" on WhatsApp
7. Entry posted to Zoho Books, GSTR-3B ITC pool updated
8. Client receives: "✓ Bill from Shree Traders ₹18,450 recorded in your books"
9. **Total time: 2 minutes (vs 15 minutes manual)**

### Journey 4: Individual Files Their First ITR

1. User opens firmOS, starts ITR flow
2. firmOS connects to IT Portal, fetches 26AS and AIS automatically
3. firmOS asks 5 questions: "Do you have capital gains? Foreign income? Business income?"
4. User uploads Form 16 (photo from phone)
5. firmOS extracts Form 16, shows summary: "Income ₹12.4L, TDS paid ₹85,000, estimated tax ₹1.08L"
6. firmOS compares old vs new regime: "Old regime saves you ₹22,000 with your 80C investments"
7. User reviews and confirms
8. firmOS files ITR-4, sends e-verification link
9. Confirmation: "ITR filed. Acknowledgement saved."

---

## 4. Features — Prioritized

### P0 — Must ship for MVP (Months 1–4)

- **Client management:** create, edit, archive clients with all credentials
- **Vendor bill processing:** WhatsApp → extraction → Zoho Books posting
- **GSTR-3B workflow:** fetch → reconcile → draft → approve → file
- **Bank reconciliation:** parse bank statement → match → BRS draft → approve
- **ITR-4 preparation:** 26AS + Form 16 → compute → draft → approve → file
- **Decision inbox:** all pending approvals, sorted by urgency
- **Agent execution log:** real-time steps view with timestamps
- **Audit trail:** immutable log of every action, exportable
- **Compliance calendar:** all deadlines per client, color-coded
- **Multi-user:** firm owner + article clerks, role-based access
- **WhatsApp bot:** bill upload + approval via WhatsApp reply

### P1 — Phase 2 (Months 5–8)

- GSTR-1 preparation and filing
- TDS return 26Q / 24Q preparation and filing
- Payroll processing (salary + PF/ESI + TDS)
- Account Aggregator integration
- Tax Audit Form 3CD preparation
- Advance tax computation + challan
- GSTR-9/9C annual return
- MCA MGT-7 and AOC-4 filing
- Bulk client approval (approve 20 clean returns in one action)

### P2 — Phase 3 (Months 9–18)

- ITR-1, ITR-2, ITR-3 (additional return types)
- Notice response drafting
- Capital gains computation (broker API)
- Form 15CA / 15CB
- PT returns (state-wise)
- Mobile approval app (iOS / Android)
- Statutory audit working papers
- Client portal (clients check their own compliance status)

---

## 5. Functional Requirements

### FR-001: Client Management

- Create client: name, PAN, GSTIN(s) (multiple for multi-state businesses), TAN, CIN, type (individual/firm/company/LLP)
- Store accounting software credentials (encrypted: Zoho OAuth token, Tally server URL)
- Store portal credentials (encrypted: GSTN username/password, IT Portal credentials)
- Import client list from CSV
- Archive clients (data retained 8 years, not deleted)
- Compliance health indicator per client (green/amber/red)

### FR-002: Compliance Calendar

- Auto-generate due dates for all active workflows per client based on client type
- Color-coded urgency: 🔴 overdue · 🟡 due < 7 days · 🟢 due > 7 days
- Send notifications 7 days and 1 day before due dates
- Mark filed on completion with acknowledgement number
- Calendar view (monthly) + list view (all upcoming)

### FR-003: Decision Inbox

- List all pending decisions sorted by: urgency → due date → client name
- Each decision shows: workflow type, client name, amount, confidence score, key insight ("2 ITC mismatches")
- Single-click approve with keyboard shortcut A
- Reject with mandatory reason dropdown (R)
- Edit before approving — triggers agent re-run with corrections (E)
- Bulk approve: select multiple clean decisions + approve all in one action
- All decisions logged immutably (approval = who, when, what was shown)

### FR-004: Agent Execution

- Show live agent steps as they run (terminal-style log with timestamps)
- Each step: action description, data source, value extracted/computed
- Agent pauses at human approval point, shows complete output
- If any step confidence < 0.85, surface to human immediately with explanation
- Maximum execution time: 10 minutes per workflow (alert if exceeded)
- Full step log preserved in audit trail even after task completion

### FR-005: Audit Trail

- Every action in system logged: data reads, computations, human approvals, portal submissions, failures
- Immutable: INSERT only, no UPDATE or DELETE permissions on audit table, ever
- Exportable as signed PDF for any client, any date range, any action type
- Filterable: by client, workflow, user, action type, date range
- Retention: minimum 8 years per Income Tax Act requirements
- Search: free-text search across all audit logs

### FR-006: Multi-User and Firm Roles

- Firm owner creates team members with assigned roles
- Article clerks can run agents and review outputs but cannot approve for government portal submission
- All actions attributed to specific named user (no anonymous actions)
- Firm owner can see all actions taken by all team members

---

## 6. Non-Functional Requirements

| Requirement | Target | Rationale |
| --- | --- | --- |
| Agent execution time | < 10 minutes per workflow | CA waits before moving to next client |
| Document extraction accuracy | > 95% | Below this, manual review defeats the purpose |
| Invoice matching accuracy | > 98% | ITC errors are costly |
| Portal submission success rate | > 99.5% | Failures on filing day are unacceptable |
| System uptime | 99.9% | < 9 hours downtime/year |
| UI response time | < 200ms for all views | Professional tool must feel instant |
| Data residency | India only (ap-south-1) | DPDP compliance |
| Encryption at rest | AES-256-GCM | Portal credentials + client financial data |
| PDF generation | < 15 seconds | Generated for every approval |
| Max clients per firm | 500 Phase 1 · 5,000 Phase 2 | Supabase RLS scales to this range |

---

## 7. Permissions Model

| Permission | Owner (CA) | Manager | Article Clerk | View Only |
| --- | --- | --- | --- | --- |
| Create / edit clients | ✓ | ✓ | — | — |
| Run agent workflows | ✓ | ✓ | ✓ | — |
| Review agent output | ✓ | ✓ | ✓ | ✓ |
| Approve (internal only) | ✓ | ✓ | — | — |
| Approve (portal filing) | ✓ | ✓ | — | — |
| Export audit trail | ✓ | ✓ | — | — |
| Manage team members | ✓ | — | — | — |
| Billing and subscription | ✓ | — | — | — |
| View audit trail | ✓ | ✓ | ✓ | ✓ |

<aside>
🔒

**Critical rule:** Only Owner and Manager can approve actions that result in government portal submissions. Article Clerks can run agents, review output, and flag for review — but the CA must always be the final approval gate for any external submission.

</aside>

---

## 8. Approval Workflows

### Standard Approval Flow

1. Agent completes execution → creates `ActionProposal` in database
2. Inbox notification: in-app + WhatsApp + email
3. Approver opens firmOS, sees complete draft + agent log
4. Decision:
    - **Approve →** agent commits to portal / accounting software → audit log entry
    - **Edit →** approver corrects specific field → agent re-runs affected steps → new proposal created
    - **Reject →** mandatory reason selection → task archived → client notified if required
5. All decisions logged with: user ID, timestamp, IP address, the exact output that was shown at time of decision

### Escalation Rules

- Primary approver inactive 48 hours → escalate to Firm Owner
- Deadline < 24 hours → urgent WhatsApp notification every 4 hours
- Portal submission fails 3 times → immediately notify Owner, mark for manual intervention
- High-risk workflow (statutory audit, 3CD) → always requires Owner approval, even if Manager initiates

---

## 9. Notifications

### WhatsApp (Primary — sent to CA's registered number)

- "8 GSTR-3B drafts ready for review. 2 need attention. [Open firmOS →]"
- "⚠ GSTR-3B for Acme Traders: 1 ITC deferred (Glow Pack ₹6,300 not in 2B)"
- "✓ Filed: GSTR-3B for 8 clients. Total paid: ₹3.4L. ARNs saved."
- "Tomorrow: GSTR-3B due for 3 clients. Not yet filed."
- "Action needed: TDS return for Kiran Supplies due in 3 days."

### In-App Notifications

- Badge count on inbox for pending approvals
- Toast notification when agent completes a workflow
- Alert when portal submission fails
- Alert when compliance deadline missed

### Email (Secondary — weekly digest)

- "This week: 8 returns filed, ₹12.4L in taxes committed, 3 new clients added"
- Monthly compliance report per client (PDF attachment)

---

## 10. Audit Trail Requirements

**Every audit log entry must contain these fields — no exceptions:**

```
timestamp          TIMESTAMPTZ, millisecond precision, UTC
firm_id            UUID
client_id          UUID (nullable for firm-level actions)
user_id            UUID (the approving human)
user_name          TEXT (denormalized for permanence)
user_role          TEXT
action_type        ENUM: DATA_READ | DOCUMENT_EXTRACTED | WORKFLOW_STARTED |
                   STEP_COMPLETED | STEP_FAILED | HUMAN_APPROVED |
                   HUMAN_REJECTED | PORTAL_SUBMITTED | PORTAL_FAILED |
                   LEDGER_POSTED | AUDIT_EXPORTED
workflow_type      TEXT (GSTR_3B | ITR_4 | VENDOR_BILL | etc.)
description        TEXT (human-readable: "GSTR-3B filed for Acme Traders, May 2026")
input_snapshot     JSONB (exact data that was used as input)
output_snapshot    JSONB (exact data that was produced)
confidence         DECIMAL (AI confidence score where applicable)
ip_address         INET
session_id         TEXT
```

**Immutability guarantee:** `audit_logs` table has `REVOKE UPDATE, DELETE ON audit_logs FROM ALL` at database level. No application code, no admin user, can ever modify an audit entry.

**Export format:** Signed PDF with: firm name, date range, total actions, entries table, SHA-256 hash of full log — suitable for tax scrutiny and ICAI peer review.

---

## 11. Success Metrics

### North Star Metric

**CA hours saved per month** (target: 40+ hours by Month 3 for active users)

### Primary Metrics

| Metric | Month 1 | Month 3 | Month 6 |
| --- | --- | --- | --- |
| Active CA firms | 3 | 10 | 25 |
| Returns filed via firmOS/month | 50 | 200 | 600 |
| CA minutes per GSTR-3B | < 8 | < 5 | < 4 |
| Agent draft acceptance rate | 75% | 88% | 93% |
| Filing error rate | 0% | 0% | 0% |
| WhatsApp bill processing time | < 3 min | < 2 min | < 90 sec |

### Secondary Metrics

- NPS (CA users): target > 50 by Month 6
- Churn rate: target < 5% monthly
- Clients per CA on firmOS: target 30+ by Month 6

---

## 12. Edge Cases

| Scenario | firmOS Handling |
| --- | --- |
| GSTN portal down on due date 20th | Auto-retry every 30 min; notify CA if down 6 hrs before deadline; manual filing instructions surfaced |
| Invoice amount in 2B differs by ₹1 (rounding) | Auto-accept difference ≤ ₹1; flag and defer if > ₹1 |
| Supplier GSTIN suspended mid-month | Flag as high risk; ITC automatically deferred; surface to CA with GSTN status check |
| GSTR-2B not available yet (supplier filed late) | Defer ITC; add to follow-up list; flag in next month's run |
| PAN not available for TDS deductee | Auto-apply higher TDS rate u/s 206AA (20%); flag for CA with explanation |
| Client switches from Zoho to Tally mid-year | Data migration tool: export Zoho, import to firmOS historical store; Tally bridge active from cutover date |
| Government portal maintenance window | Pre-check portal status before scheduling; route to off-peak window; never fail silently |
| Network failure mid-portal-submission | Idempotency key generated before submission; check portal for existing filing before any retry; never double-file |
| CA forgets to approve before deadline | Escalation chain + hourly WhatsApp alerts in last 6 hours; flag in dashboard as OVERDUE |
| New GST rule changes effective mid-year | Version-controlled rule engine; rules tagged with effective dates; old rules preserved for past-period filings |
| Article clerk tries to approve a portal filing | Hard block at API level with clear message: "Only Owner/Manager can approve portal filings. Notify [Owner Name]." |