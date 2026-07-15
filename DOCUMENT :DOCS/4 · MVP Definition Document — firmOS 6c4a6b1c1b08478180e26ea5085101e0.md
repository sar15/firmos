# 4 · MVP Definition Document — firmOS

## firmOS · MVP Definition Document

**Version 1.0 · June 2026 · Execution-ready**

<aside>
🎯

This document defines exactly what gets built in the first 90 days. Every decision has a "why." Nothing is included for theoretical completeness. Nothing is excluded without a plan for when it arrives.

</aside>

---

## 1. The MVP Does Exactly Four Things, Perfectly

1. **Vendor Bill Processing** — WhatsApp photo → extracted → validated → posted to Zoho Books
2. **GSTR-3B Filing** — 2B fetch → reconcile → draft → CA approves → file to GSTN
3. **Bank Reconciliation** — bank statement → match vs books → BRS → CA approves
4. **ITR-4 Filing** — 26AS + Form 16 → compute tax → draft → CA approves → file

**Why these four?**

- Cover 80% of monthly CA time for a typical 40-client firm
- Highest frequency — GSTR-3B is monthly, vendor bills are daily, ITR is annual but high-value
- Fully definable — clear input → clear logic → clear output → clear portal
- Independently verifiable — CA can immediately confirm if it's right
- Together they tell the complete firmOS story to an investor, pilot CA, or early adopter
- Each one alone saves 20-40 hours/month per CA — undeniable, measurable ROI

---

## 2. What Is Intentionally Excluded (and When It Arrives)

| Excluded from MVP | Reason | When |
| --- | --- | --- |
| GSTR-1 filing | Needs IRN/e-invoice integration (+3 weeks). GSTR-3B alone proves the GST automation model. | Month 5 |
| TDS returns (26Q/24Q) | Separate portal (TRACES), FVU format. Not needed to prove product. | Month 5 |
| Payroll processing | Complex state PT variations. High value but low urgency for pilot firms. | Month 6 |
| Tax Audit 3CD | Requires finalized accounts. Annual workflow. Wrong timing for MVP. | Month 7 |
| MCA/ROC filings | Low frequency (annual). No urgency for pilot. | Month 7 |
| GSTR-9/9C | Depends on 12 months of GSTR-3B data. Build after data exists. | Month 14 |
| Tally integration | Zoho Books API is cleaner and faster to integrate. Tally adds 3-4 weeks. | Month 5 |
| Account Aggregator | AA framework approval takes 3-4 months. Use manual bank statement upload first. | Month 6 |
| Mobile app | Web app sufficient for CA workflows at desk. Mobile = approval on phone, Phase 3. | Month 12 |
| Multi-firm support | Single firm first. Add multi-firm after product-market fit proven. | Month 6 |
| Capital gains computation | Needs broker API integrations. ITR-4 covers business income cases first. | Month 8 |
| Notice response | High complexity, low frequency in MVP set. | Month 9 |
| Client-facing portal | Clients use WhatsApp to submit. Portal adds scope without changing core proof. | Month 9 |

---

## 3. MVP Workflow 1: Vendor Bill Processing

**Goal:** Client sends vendor bill on WhatsApp → appears in Zoho Books as a purchase entry with zero manual work.

**Step-by-step flow:**

```
[Client]
  ↓ Photos vendor bill on WhatsApp

[firmOS WhatsApp Bot — Meta Business API]
  ↓ Receives image, stores in Supabase Storage
  ↓ Acknowledges: "Got it. Processing your bill..."

[Document Pipeline — Gemini 3.1 Flash-Lite Vision]
  ↓ Extract: vendor_name, vendor_gstin, invoice_number, invoice_date,
             taxable_amount, cgst, sgst, igst, total_amount
  ↓ Confidence score per field

[Validation Engine — Python rules]
  ↓ GSTIN checksum validation (modular 97 algorithm)
  ↓ Arithmetic check: taxable + cgst + sgst = total ±₹1
  ↓ Duplicate check: same vendor + same invoice number + same amount in last 90 days
  ↓ Date validity: not future-dated, not older than 2 years
  ↓ If any validation fails: flag for human review with specific reason

[Action Proposal Created]
  ↓ Decision record: "Approve vendor bill: Shree Traders ₹18,450 dated 15 Jun"
  ↓ WhatsApp to CA: "New bill from Shree Traders ₹18,450 ready for approval"

[CA Approves]
  ↓ Option 1: Click Approve in firmOS inbox
  ↓ Option 2: Reply "1" on WhatsApp
  ↓ Approval logged: user ID, timestamp, IP address

[Commit]
  ↓ POST to Zoho Books: create purchase entry
  ↓ Tags: vendor, amount, tax amounts, GSTIN
  ↓ Client WhatsApp confirmation: "✓ Bill from Shree Traders ₹18,450 recorded"
  ↓ Audit log entry written
```

**Error handling:** If Zoho Books API fails → retry 3x → notify CA with manual entry instructions. If WhatsApp image unreadable → ask client to resend or upload via web portal.

**Build vs Buy:**

- WhatsApp Business API: **Buy** (Meta Cloud API, free first 1,000 conversations/month)
- Gemini Vision: **Buy** (Vertex AI, ~₹1.5 per 100 documents)
- Zoho Books API: **Buy** (included in Zoho Books subscription)
- Validation engine: **Build** (Python, ~2 days)
- GSTIN checksum: **Build** (Python, 2 hours, algorithm is public)

---

## 4. MVP Workflow 2: GSTR-3B Preparation and Filing

**Goal:** Complete GSTR-3B for a client in 5 minutes of CA review time, filed accurately.

**Step-by-step flow:**

```
[Trigger]
  ↓ Calendar: 8 days before 20th of month, OR
  ↓ Manual: CA types "GSTR-3B for Acme" in command input

[Data Collection]
  ↓ Login to GSTN portal (Playwright, stored session)
  ↓ Download GSTR-2B (CSV/JSON for the period)
  ↓ Fetch purchase register from Zoho Books API
  ↓ Fetch sales register from Zoho Books API

[Reconciliation Engine — Python]
  ↓ Parse GSTR-2B: extract all supplier invoices
  ↓ Parse purchase register: all vendor bills for the period
  ↓ Match on: GSTIN exact + invoice number fuzzy + amount ±₹1
  ↓ Status per invoice: MATCHED | UNMATCHED_2B | UNMATCHED_BOOKS | AMOUNT_DIFF
  ↓ Compute eligible ITC: only MATCHED invoices
  ↓ Defer flagged ITC: UNMATCHED_2B invoices
  ↓ Vendor follow-up list: sorted by deferred ITC amount

[Tax Computation — Deterministic Python, never AI]
  ↓ Output tax: sum of CGST + SGST + IGST from sales register
  ↓ ITC eligible: sum of CGST + SGST + IGST from matched purchase invoices
  ↓ Net payable: output tax - eligible ITC
  ↓ Interest if late (if applicable)
  ↓ Generate challan amount if net payable > 0

[Draft Generation]
  ↓ Populate GSTR-3B tables (3.1 to 5) per GSTN JSON schema
  ↓ Generate human-readable PDF summary
  ↓ Confidence score: based on match rate (95%+ matched = High)

[Human Approval Checkpoint — LangGraph interrupt()]
  ↓ Action proposal created: "Approve GSTR-3B for Acme Traders — ₹41,600 payable"
  ↓ CA sees: mismatch list, computation breakdown, challan amount
  ↓ CA decision: Approve / Edit / Reject

[Commit on Approval]
  ↓ Login to GSTN portal (Playwright)
  ↓ Navigate to GSTR-3B filing for the period
  ↓ Fill all tables from computed JSON
  ↓ Submit, handle OTP if required (notify CA)
  ↓ Store ARN (Acknowledgement Reference Number)
  ↓ Mark compliance calendar: FILED
  ↓ Audit log entry with full input/output snapshot
```

**Critical implementation notes:**

- Idempotency key generated before GSTN portal submission. Before filling the form, check if return is already submitted for this period. Never double-file.
- If GSTN portal is down: queue for retry every 30 minutes. If still down 6 hours before midnight on due date, escalate to CA with manual instructions.
- OTP during filing: pause automation, notify CA to enter OTP on portal, then resume.
- GSTN portal changes UI frequently: maintain selectors in a config file, not hardcoded in automation script. Monitor for failures.

**Build vs Buy:**

- Playwright portal automation: **Build** (2-3 weeks for GSTN)
- Reconciliation engine: **Build** (Python, 1 week)
- GSTR-3B JSON schema: **Build** (per GSTN spec, 3 days)
- PDF generation: **Buy** (ReportLab, pip install)
- LangGraph interrupt: **Buy** (open-source, pip install)

---

## 5. MVP Workflow 3: Bank Reconciliation

**Goal:** Match all bank transactions against ledger entries, produce BRS in 5 minutes.

**Step-by-step flow:**

```
[Input]
  ↓ CA uploads bank statement PDF (or CSV if bank exports it)

[Bank Statement Parsing]
  ↓ Detect format: PDF / CSV / Excel
  ↓ If PDF: Gemini Vision extracts table of transactions
     (date, description, debit/credit/balance columns)
  ↓ If CSV: parse directly (pandas)
  ↓ Output: structured list of transactions [{date, narration, amount, type, balance}]

[Ledger Fetch]
  ↓ Fetch bank account ledger from Zoho Books API for the same period
  ↓ Output: list of ledger entries with same structure

[Matching Engine — Python]
  ↓ Phase 1: Exact match (amount + date exact)
  ↓ Phase 2: Near match (amount exact + date ±3 days)
  ↓ Phase 3: Fuzzy narration (amount exact + RapidFuzz narration similarity >85%)
  ↓ Result per transaction: MATCHED | UNMATCHED_BANK | UNMATCHED_BOOKS
  ↓ Compute closing balance difference
  ↓ Flag round-number unmatched items (possible fraud indicator)

[BRS Generation]
  ↓ Bank Reconciliation Statement PDF:
     - Opening balance
     - Matched transactions count + amount
     - Unmatched bank entries (list with amounts)
     - Unmatched book entries (list with amounts)
     - Closing balance per bank
     - Closing balance per books
     - Difference

[Human Approval]
  ↓ CA reviews unmatched items
  ↓ For each unmatched item: CA can mark as "Post to Books" or "Reconciling Item"
  ↓ CA approves final BRS
  ↓ Any "Post to Books" items: agent creates Zoho Books entries on approval

[Audit log entry written]
```

**Build vs Buy:**

- PDF parsing: **Buy** (Gemini Vision)
- Matching engine: **Build** (Python + RapidFuzz, 3 days)
- BRS PDF template: **Build** (ReportLab, 1 day)
- Zoho Books ledger fetch: **Buy** (Zoho API)

---

## 6. MVP Workflow 4: ITR-4 Filing

**Goal:** File ITR-4 for a client with business income, with CA review in < 10 minutes.

**Step-by-step flow:**

```
[Data Collection]
  ↓ Login to IT Portal (Playwright)
  ↓ Fetch Form 26AS (PDF download + parse)
  ↓ Fetch AIS — Annual Information Statement (PDF/JSON)
  ↓ CA uploads Form 16 (PDF)
  ↓ CA enters business income summary (structured form: gross receipts, presumptive income %)

[Document Processing]
  ↓ Gemini Vision extracts Form 16:
     employer name, PAN, gross salary, allowances, perquisites,
     deductions u/s 16, net taxable salary, TDS amount
  ↓ Parse 26AS: TDS deducted by all deductors, advance tax paid
  ↓ Parse AIS: interest income, dividends, capital gains (flag if present — needs ITR-2 not ITR-4)

[Tax Computation — Deterministic Python]
  ↓ Income classification:
     - Salary income (from Form 16)
     - Business income (from CA input, presumptive u/s 44AD/44ADA)
     - Other income (interest, dividends from AIS)
  ↓ Deduction computation:
     - 80C (declared by client or CA)
     - 80D (health insurance premium)
     - 80CCD(1B) (NPS)
     - 24(b) (home loan interest, if applicable)
  ↓ Compute taxable income under old and new regime
  ↓ Compute tax + surcharge + cess under both
  ↓ Recommend: whichever regime results in lower tax
  ↓ Compute net payable: tax - TDS (from 26AS) - advance tax
  ↓ Compute interest u/s 234B and 234C if advance tax shortfall

[ITR-4 JSON Generation]
  ↓ Populate all schedules per IT Department JSON schema:
     - Part A General: personal info
     - Schedule BP: business income
     - Schedule S: salary income
     - Schedule OS: other income
     - Schedule VIA: deductions
     - Part B-TTI: tax computation
  ↓ Validate JSON against schema
  ↓ Generate PDF draft for CA review

[Human Approval — LangGraph interrupt()]
  ↓ CA sees: income summary, deductions, tax computed, regime recommendation
  ↓ CA reviews and approves (or adjusts specific fields)
  ↓ Approval logged

[Commit on Approval]
  ↓ Login to IT Portal (Playwright)
  ↓ Upload ITR JSON
  → Submit
  ↓ Store acknowledgement number
  ↓ Send e-verification link to client via WhatsApp
  ↓ Audit log entry written
```

**Build vs Buy:**

- IT Portal automation: **Build** (Playwright, 2 weeks)
- Form 16 extraction: **Buy** (Gemini Vision)
- Tax computation engine: **Build** (Python, 1 week, fully tested)
- ITR JSON schema: **Build** (per IT Dept spec, 1 week)
- E-verification flow: **Build** (Playwright or WhatsApp OTP link)

---

## 7. Screens and User Flows

### Screen 1: Command Home

- Personalized greeting with date
- Big command input: "What do you need to do today?"
- 4 suggestion chips: most urgent pending tasks
- Work queue: all pending decisions sorted by urgency + due date
- Recent completions (last 3 filings)
- Keyboard shortcut ⌘K focuses command input

### Screen 2: Decision Inbox

- Left column: work queue list (permanent, 280px)
- Right column: selected task detail
- Task rows: 3-line format (name, client, amount/due date)
- 3px colored left strip by workflow type
- Keyboard: J/K to navigate, A to approve, R to reject, E to edit

### Screen 3: Agent Execution View

- Top bar: task name + client chip + live status + timer
- Left panel: live agent log (terminal-style, monospace, timestamps)
- Right panel: output document (ledger format, monospace amounts)
- Bottom bar: Approve A · Edit E · Reject R · trust note

### Screen 4: Client Profile

- Client details (name, PAN, GSTIN, accounting software)
- Compliance calendar (list of all due dates)
- Filing history (last 12 months)
- Active workflows (running or pending approval)

### Screen 5: Audit Log

- Filter by client, workflow type, date range, action type
- Each entry: timestamp, user, action, description, data snapshot
- Export as PDF button
- Read-only (no edit/delete actions)

### Mobile (web-responsive only in MVP)

- Sidebar hidden, full-width content
- Agent log and output stack vertically
- WhatsApp remains primary mobile interaction channel

---

## 8. Technical Architecture

```
Browser (Next.js 15)
      ↓ HTTPS
FastAPI (Python 3.12) — Railway
      ↓
┌────────────┬───────────────┬─────────────┐
│  Supabase   │  LangGraph    │  Vertex AI   │
│  Postgres   │  Worker       │  Gemini 3.1  │
│  + Storage  │  (Railway)    │  Flash-Lite  │
│  + Auth     │  + Redis      │  asia-south1 │
└────────────┴───────────────┴─────────────┘
                      ↓
           ┌─────────────────────────┐
           │  Playwright Browser Bot  │
           │  (Railway Docker)        │
           │  GSTN Portal             │
           │  IT Portal               │
           │  TRACES Portal           │
           └─────────────────────────┘
           ┌─────────────────────────┐
           │  External APIs           │
           │  Zoho Books OAuth        │
           │  WhatsApp Meta API       │
           └─────────────────────────┘
```

**Stack rationale:**

- **Next.js 15 on Vercel:** Instant deploys, free tier for MVP, React Server Components for fast UI, built-in API routes for simple webhooks
- **FastAPI + Python:** Best ecosystem for AI, document processing, and financial rules engines. Async for concurrent workflow execution.
- **Supabase:** Postgres + Row Level Security (firm isolation) + Storage (documents) + Auth (users). Single vendor for most data needs. Free tier gets you to 50K rows, $25/month after.
- **LangGraph 1.0:** Best open-source framework for multi-step agent workflows with human-in-the-loop interrupts. `interrupt()` is exactly what we need for the approval gate.
- **Playwright:** Open-source, most reliable for government portals. Better than Selenium for modern JS-heavy sites.
- **Gemini 3.1 Flash-Lite on Vertex AI (asia-south1):** Cheapest vision-capable model, India data residency for DPDP.

---

## 9. Data Model — Core Tables

### firms

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
name TEXT NOT NULL,
gstin TEXT,
pan TEXT,
plan TEXT DEFAULT 'trial',  -- trial | starter | pro
zoho_client_id TEXT,
zoho_refresh_token_encrypted TEXT,
gstn_username TEXT,
gstn_password_encrypted TEXT,  -- AES-256-GCM at app layer
it_portal_username TEXT,
it_portal_password_encrypted TEXT,
whatsapp_number TEXT,
created_at TIMESTAMPTZ DEFAULT NOW()
```

### clients

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
firm_id UUID REFERENCES firms(id) NOT NULL,
name TEXT NOT NULL,
pan TEXT,
gstin TEXT[],  -- array: multiple states
tan TEXT,
cin TEXT,
client_type TEXT,  -- individual | firm | company | llp
accounting_software TEXT,  -- zoho | tally | none
zoho_organization_id TEXT,
status TEXT DEFAULT 'active',  -- active | archived
created_at TIMESTAMPTZ DEFAULT NOW()
```

### action_proposals

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
firm_id UUID NOT NULL,
client_id UUID NOT NULL,
workflow_type TEXT NOT NULL,  -- GSTR_3B | ITR_4 | VENDOR_BILL | BANK_RECON
period TEXT,  -- '2026-05' for May 2026
status TEXT DEFAULT 'pending',  -- pending | approved | rejected | committed | failed
confidence DECIMAL(3,2),  -- 0.00 to 1.00
agent_input JSONB,  -- all data collected by agent
agent_output JSONB,  -- draft produced by agent
agent_log JSONB[],  -- array of step log entries
flags JSONB[],  -- items needing human attention
decision_note TEXT,  -- CA's reason for rejection
commit_result JSONB,  -- portal response, ARN, etc.
idempotency_key TEXT UNIQUE,
langgraph_thread_id TEXT,
created_at TIMESTAMPTZ DEFAULT NOW(),
decided_at TIMESTAMPTZ,
decided_by UUID REFERENCES users(id),
committed_at TIMESTAMPTZ
```

### documents

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
firm_id UUID NOT NULL,
client_id UUID NOT NULL,
doc_type TEXT NOT NULL,  -- vendor_bill | bank_statement | form_16 | notice
storage_path TEXT NOT NULL,  -- Supabase Storage path
extracted_data JSONB,
extraction_confidence DECIMAL(3,2),
uploaded_via TEXT,  -- whatsapp | web | api
uploaded_by UUID,
created_at TIMESTAMPTZ DEFAULT NOW()
```

### audit_logs

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
firm_id UUID NOT NULL,
client_id UUID,
user_id UUID NOT NULL,
user_name TEXT NOT NULL,  -- denormalized for permanence
action_type TEXT NOT NULL,
workflow_type TEXT,
description TEXT NOT NULL,
input_snapshot JSONB,
output_snapshot JSONB,
confidence DECIMAL(3,2),
ip_address INET,
session_id TEXT
-- NO UPDATE/DELETE EVER. REVOKED AT DATABASE LEVEL.
```

### compliance_calendar

```sql
id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
firm_id UUID NOT NULL,
client_id UUID NOT NULL,
workflow_type TEXT NOT NULL,
return_period TEXT NOT NULL,  -- '2026-05'
due_date DATE NOT NULL,
status TEXT DEFAULT 'pending',  -- pending | in_progress | filed | overdue
filed_at TIMESTAMPTZ,
acknowledgement_number TEXT,
action_proposal_id UUID REFERENCES action_proposals(id)
```

---

## 10. Monthly Infrastructure Cost

### MVP Phase (Months 1–4): 3–10 CA firms

| Service | Plan | Monthly Cost | Notes |
| --- | --- | --- | --- |
| Vercel | Hobby / Pro | $0–$20 | Next.js frontend + CDN |
| Railway | Starter | $20 | FastAPI API + LangGraph worker |
| Supabase | Free → Pro | $0–$25 | Postgres + Storage + Auth |
| Upstash Redis | Free | $0 | Job queue, free tier sufficient |
| Vertex AI (Gemini) | Pay-per-use | $20–50 | ~50K document extractions/month |
| WhatsApp Business | Meta Cloud | $0–20 | 1,000 free conversations/month |
| Sentry | Free | $0 | Error monitoring |
| **Total** |  | **$60–$115** |  |

### Growth Phase (Months 5–8): 20–50 CA firms, 500–1,000 clients

| Service | Plan | Monthly Cost |
| --- | --- | --- |
| Vercel Pro | Pro | $20 |
| Railway Pro | Pro | $100 (3 services) |
| Supabase Pro | Pro | $25 |
| Vertex AI | Pay-per-use | $150 |
| WhatsApp | Meta Cloud | $80 |
| **Total** |  | **~$375** |

### Revenue vs Cost

**At 50 CA firms, 500 clients (₹3,000/client/year):**

- Revenue: 500 × ₹3,000 = **₹15L/year = ₹1.25L/month**
- Infrastructure: ~₹31,000/month
- **Gross margin: 75%** (growing toward 90%+ at scale)

---

## 11. Team Requirements

### MVP Team (4 people, Months 1–4)

| Role | Allocation | Responsibilities |
| --- | --- | --- |
| **Founder / PM** | Full-time | Product decisions, CA user interviews, sales, pilot onboarding, content |
| **Full-Stack Engineer** | Full-time | Next.js frontend, FastAPI backend, Supabase schema, API integrations |
| **AI / Automation Engineer** | Full-time | LangGraph workflows, Gemini integrations, Playwright portal automation |
| **CA Domain Expert** | Part-time (10 hrs/week) | Validate all tax logic, review computed outputs, test edge cases |

**Hiring priority:** AI/Automation Engineer is the most critical technical hire. Playwright + LangGraph + Gemini is a specific skill set. Look for Python engineers with experience in browser automation and LLM integration.

**What the founder does:** Every pilot CA onboarding is done personally by the founder. Sit with them. Watch them use firmOS. Fix what breaks in real-time. The first 10 customers are a product design exercise, not a sales exercise.

---

## 12. 30 / 60 / 90-Day Execution Plan

### Days 1–30: Infrastructure + First Vendor Bill

**Milestone: First real vendor bill processed end-to-end. CA approves in firmOS, entry appears in Zoho Books.**

- [ ]  Supabase project created, schema migrated, RLS policies set
- [ ]  FastAPI skeleton with auth (Supabase JWT)
- [ ]  Zoho Books OAuth integration (read + write purchase entries)
- [ ]  Gemini Vision integration — vendor bill extraction working
- [ ]  GSTIN validation algorithm (Python)
- [ ]  WhatsApp Business API setup + webhook handler
- [ ]  Bill extraction pipeline: WhatsApp image → Gemini → structured JSON
- [ ]  Basic Next.js UI: decision inbox + agent execution view
- [ ]  First end-to-end test: WhatsApp bill → extraction → approve → Zoho Books
- [ ]  Deploy to Railway + Vercel
- [ ]  Onboard 2 pilot CA firms from personal network
- [ ]  Audit log table setup and first entries

**Day 30 success criteria:** One real client's vendor bill processed through firmOS. CA approves. Entry appears in Zoho Books. Zero manual work. Audit log shows every step.

---

### Days 31–60: GSTR-3B End-to-End

**Milestone: First GSTR-3B filed through firmOS for a real client. CA approves in < 5 minutes.**

- [ ]  Playwright setup with Chromium in Docker on Railway
- [ ]  GSTN portal login automation (handle 2FA if present)
- [ ]  GSTR-2B download automation
- [ ]  2B vs purchase ledger reconciliation engine (Python)
- [ ]  GSTR-3B tax computation (deterministic rules engine)
- [ ]  GSTR-3B JSON generator (per GSTN schema)
- [ ]  GSTR-3B PDF draft generator (ReportLab)
- [ ]  LangGraph workflow for complete GSTR-3B flow
- [ ]  LangGraph `interrupt()` — human approval gate
- [ ]  GSTR-3B portal filing automation (Playwright)
- [ ]  Compliance calendar (deadlines, due date triggers)
- [ ]  Monthly auto-trigger for all clients (cron job)
- [ ]  End-to-end test with real client's data (test period first)
- [ ]  WhatsApp notification: "GSTR-3B ready for review"

**Day 60 success criteria:** GSTR-3B filed through firmOS for a real client. End-to-end time: < 15 minutes total. CA review time: < 5 minutes. ARN stored. Audit log complete.

---

### Days 61–90: ITR-4 + Bank Recon + Launch

**Milestone: 5 paying CA firms, 50+ clients, ₹5L ARR committed. All 4 MVP workflows in production.**

- [ ]  IT Portal login automation (Playwright)
- [ ]  26AS and AIS download automation
- [ ]  Form 16 PDF extraction (Gemini Vision, structured schema)
- [ ]  Income tax computation engine (old vs new regime, all slabs, all sections)
- [ ]  ITR-4 JSON generation (per IT Dept schema, validation)
- [ ]  ITR-4 portal filing automation
- [ ]  Bank statement PDF parsing (Gemini Vision)
- [ ]  Bank reconciliation matching engine (RapidFuzz)
- [ ]  BRS PDF generator
- [ ]  Full audit trail view (filterable, exportable as PDF)
- [ ]  Client profile page with compliance calendar
- [ ]  Onboard 3 more CA firms (target: 5 total, 50 clients)
- [ ]  First paid invoices sent and collected
- [ ]  Error monitoring live (Sentry)
- [ ]  Uptime monitoring live (Better Uptime or UptimeRobot)

**Day 90 success criteria:** 5 CA firms paying. 50 clients active on firmOS. All 4 workflows in production. Zero filing errors. CA time savings documented and quantified. NPS > 40 from pilot users.

<aside>
⚠️

**The most important rule:** Do not move to Day 31 tasks until Day 30 milestone is genuinely achieved with a real client. Do not start GSTR-3B until vendor bills are production-quality and error-free. Each workflow is a commitment to a CA's professional practice. Get each one right before adding the next.

</aside>