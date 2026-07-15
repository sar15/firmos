# 10 · Complete Workflow & Input Method Plan — firmOS

## firmOS · Every Workflow, Every Input Method

**Version 1.0 · June 2026 · Comprehensive**

---

## The Key Insight

**Every workflow can accept data via multiple input methods:**

| Input Method | How It Works | When to Use |
|-------------|-------------|-------------|
| **API** | Direct connection to accounting software | Zoho Books, QuickBooks, CAMS |
| **Playwright** | Browser automation for government portals | GSTN, IT Portal, TRACES, MCA21 |
| **WhatsApp** | Client sends photos/docs via WhatsApp | Vendor bills, notices, documents |
| **PDF Upload** | Accountant uploads PDF documents | Bank statements, Form 16, trial balance |
| **CSV/Excel Upload** | Accountant uploads spreadsheets | Bank statements, employee data, transactions |
| **Manual Entry** | Accountant enters data in a form | Missing data, corrections, edge cases |

**The pattern:** Agent does the extraction and processing. Human uploads the source document. Agent does the rest.

---

## Complete Workflow × Input Method Matrix

### Workflow 1: Vendor Bill Processing

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **WhatsApp photo** | Client photos bill → WhatsApp → firmOS | Extract fields → validate → post to Zoho Books | Approve |
| **PDF upload** | Accountant uploads PDF → firmOS | Gemini Vision extracts → validate → post | Approve |
| **Web upload** | Accountant uploads via firmOS UI → firmOS | Gemini Vision extracts → validate → post | Approve |

**Data extracted from vendor bill:**
- vendor_name, vendor_gstin, invoice_number, invoice_date
- taxable_amount, cgst, sgst, igst, total_amount
- Line items (quantity, rate, HSN code)

**Validation engine (Python rules, not AI):**
- GSTIN checksum (modular 97 algorithm)
- Arithmetic: taxable + cgst + sgst + igst = total ±₹1
- Duplicate check: same vendor + same invoice number + same amount in 90 days
- Date validity: not future-dated, not older than 2 years

**Connector needed:** Zoho Books API (post purchase entry)

---

### Workflow 2: Bank Reconciliation

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **PDF upload** | Accountant uploads bank statement PDF | Gemini Vision extracts transactions → match vs books → BRS | Review unmatched, approve BRS |
| **CSV upload** | Accountant uploads bank CSV export | Parse CSV → match vs books → BRS | Review unmatched, approve BRS |
| **Account Aggregator** | Agent fetches bank data via AA API | Fetch transactions → match vs books → BRS | Review unmatched, approve BRS |
| **WhatsApp** | Client sends bank statement photo | Gemini Vision extracts → match → BRS | Review unmatched, approve BRS |

**Data extracted from bank statement:**
- Transaction date, narration/description, debit, credit, balance
- Account number, IFSC code

**Matching engine (Python rules):**
- Phase 1: Exact match (amount + date exact)
- Phase 2: Near match (amount exact + date ±3 days)
- Phase 3: Fuzzy narration (amount exact + RapidFuzz narration similarity >85%)
- Flag: unmatched bank entries, unmatched book entries, duplicates, round-number anomalies

**Output:** BRS PDF with opening balance, matched/unmatched items, closing balance

**Connector needed:** Zoho Books API (fetch bank ledger), Gemini Vision (PDF extraction)

---

### Workflow 3: GSTR-3B Filing

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **API** | Agent fetches 2B from GSTN, purchase/sales from Zoho Books | Fetch → reconcile → compute → draft → file | Approve mismatches, approve filing |
| **Playwright** | Agent logs into GSTN portal, downloads 2B | Fetch 2B → reconcile → compute → draft → file | Approve mismatches, approve filing |
| **PDF upload** | Accountant uploads 2B PDF, purchase register PDF | Gemini Vision extracts → reconcile → compute → draft | Approve mismatches, approve filing |

**Data sources:**
- GSTR-2B (auto-populated supplier invoices) — from GSTN API or Playwright
- Purchase ledger — from Zoho Books API or uploaded PDF/CSV
- Sales ledger — from Zoho Books API or uploaded PDF/CSV

**Matching engine:**
- Match each purchase invoice against 2B: PAN + invoice number + amount ±₹1
- Flag: not in 2B, amount difference, GSTIN format error
- Defer ITC for mismatched invoices

**Computation engine (deterministic Python, never AI):**
- Output tax from sales register
- Eligible ITC (only 2B-confirmed invoices)
- Net payable = output tax - eligible ITC
- Challan amount if payable > 0

**Connector needed:** GSTN Portal (Playwright or GSP API), Zoho Books API, Gemini Vision

---

### Workflow 4: GSTR-1 Filing

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **API** | Agent fetches sales invoices from Zoho Books | Fetch → classify → validate → reconcile → draft → file | Approve classification exceptions, approve filing |
| **PDF upload** | Accountant uploads sales register PDF | Gemini Vision extracts → classify → validate → reconcile → draft | Approve exceptions, approve filing |
| **CSV upload** | Accountant uploads sales CSV | Parse → classify → validate → reconcile → draft | Approve exceptions, approve filing |

**Data extracted:**
- Invoice number, date, customer GSTIN, taxable amount, tax amounts
- HSN codes, place of supply

**Classification engine:**
- B2B (with GSTIN), B2C large (>₹2.5L), B2C small, exports, nil-rated, exempted

**Connector needed:** GSTN Portal (Playwright or GSP API), Zoho Books API, IRP API (e-invoice)

---

### Workflow 5: ITR Filing

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **Playwright** | Agent fetches 26AS, AIS from IT Portal | Fetch → parse → compute tax → draft → file | Approve regime selection, approve filing |
| **PDF upload** | Accountant uploads Form 16, 26AS, AIS | Gemini Vision extracts → compute tax → draft | Approve regime, approve filing |
| **WhatsApp** | Client sends Form 16 photo | Gemini Vision extracts → compute tax → draft | Approve regime, approve filing |
| **API** | Agent fetches capital gains from CAMS/brokers | Fetch → compute → draft | Approve CG classification, approve filing |

**Data sources:**
- Form 26AS (TDS deducted, advance tax paid) — from IT Portal or uploaded PDF
- AIS (Annual Information Statement) — from IT Portal or uploaded PDF
- Form 16 (employer, salary details) — uploaded PDF or WhatsApp photo
- Capital gains statements — from CAMS/brokers API or uploaded PDF
- Business P&L — from Zoho Books or uploaded

**Computation engine (deterministic Python, never AI):**
- Income classification with correct schedule
- Deduction computation (80C, 80D, 80CCD)
- Tax under old regime vs new regime — recommend optimal
- Interest u/s 234B and 234C if advance tax missed

**Connector needed:** IT Portal (Playwright), Zoho Books API, CAMS API, Gemini Vision

---

### Workflow 6: TDS Return (26Q / 24Q)

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **API** | Agent fetches deduction register from Zoho Books | Compile → validate PANs → match challans → generate FVU → file | Approve short deductions, approve filing |
| **PDF upload** | Accountant uploads deduction register PDF | Gemini Vision extracts → validate → match → generate FVU | Approve, approve filing |
| **CSV upload** | Accountant uploads deduction CSV | Parse → validate PANs → match → generate FVU | Approve, approve filing |

**Data extracted:**
- Deductee name, PAN, section, payment date, payment amount, TDS deducted
- Challan BSR code, challan date, challan amount

**Computation engine:**
- Validate all PANs via IT Portal API
- Match challans with deductions via TRACES
- Identify short deductions, late deposits
- Compute interest u/s 201A and late filing fee u/s 234E
- Generate FVU file in NSDL format

**Connector needed:** TRACES (Playwright), IT Portal (Playwright), Zoho Books API

---

### Workflow 7: Payroll Processing

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **CSV upload** | Accountant uploads attendance CSV | Compute salary → deduct PF/ESI/TDS → generate payslips → ECR | Approve variable pay, approve bank transfer |
| **API** | Agent fetches attendance from HR system | Compute → deduct → generate → ECR | Approve variable pay, approve transfer |
| **Manual entry** | Accountant enters attendance in firmOS form | Compute → deduct → generate → ECR | Approve, approve transfer |

**Computation engine:**
- Gross salary (basic + HRA + allowances + overtime)
- PF: 12% employee + 13% employer (EPFO ECR format)
- ESI: 0.75% employee + 3.25% employer (salary < ₹21,000)
- TDS on salary using projected annual income method
- Professional Tax (state-specific slabs)

**Outputs:** Payslips (PDF), EPFO ECR file, ESI return file, bank NEFT transfer file

**Connector needed:** EPFO portal (Playwright), ESIC portal (Playwright), Zoho Books API

---

### Workflow 8: Tax Audit 3CD

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **API** | Agent fetches trial balance from Zoho Books | Auto-populate 30/44 clauses → flag CA-required clauses | Review ALL 44 clauses, complete remaining 14, sign |
| **PDF upload** | Accountant uploads trial balance PDF | Gemini Vision extracts → auto-populate 30/44 clauses | Review ALL 44, complete remaining, sign |
| **Excel upload** | Accountant uploads trial balance Excel | Parse → auto-populate 30/44 clauses | Review ALL 44, complete remaining, sign |

**Clauses auto-populated (30 of 44):**
- Clause 13: Method of accounting
- Clause 14: Valuation of closing stock
- Clause 15: Profit / turnover
- Clause 17: Land and building purchases
- Clause 21: Deductions claimed
- Clause 26: Cash payments > ₹20,000 (Sec 40A)
- Clause 27: Payments to specified persons
- Clause 34: TDS compliance
- Clause 36B: MSMED compliance

**Clauses requiring CA judgment (14 of 44):**
- Clause 16, 19, 30, 40, and others requiring professional opinion

**Connector needed:** Zoho Books API, IT Portal (Playwright), Gemini Vision

---

### Workflow 9: MCA / ROC Annual Filings

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **API** | Agent fetches company data from MCA21 | Populate MGT-7 + AOC-4 → generate XML | Directors approve, CA signs, DSC signs |
| **PDF upload** | Accountant uploads audited financial statements | Gemini Vision extracts → populate MGT-7 + AOC-4 | Directors approve, CA signs |

**Connector needed:** MCA21 Portal (Playwright), Gemini Vision

---

### Workflow 10: Notice Response

| Input Method | Flow | Agent Does | Human Does |
|-------------|------|-----------|-----------|
| **WhatsApp** | Client sends notice photo | Gemini Vision extracts → classify → draft response | CA reviews ALL, decides strategy, signs |
| **PDF upload** | Accountant uploads notice PDF | Gemini Vision extracts → classify → draft response | CA reviews ALL, decides strategy, signs |
| **Playwright** | Agent downloads notice from IT/GST portal | Classify → pull relevant data → draft response | CA reviews ALL, decides strategy, signs |

**Notice types handled:**
- 143(1) — intimation of differences
- 148 — reassessment notice
- 245 — demand notice
- 139(9) — defective return notice
- GSTN mismatch notice
- TRACES demand notice

**Connector needed:** IT Portal (Playwright), GSTN Portal (Playwright), TRACES (Playwright), Gemini Vision

---

## The Document Pipeline (Shared Across All Workflows)

```
┌─────────────────────────────────────────────────────────┐
│                  DOCUMENT INPUT                          │
│  WhatsApp photo / PDF upload / CSV upload / API fetch   │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              CLASSIFICATION                              │
│  Gemini Flash-Lite: "What type of document is this?"    │
│  Options: vendor_bill | bank_statement | form_16 |      │
│           notice | trial_balance | deduction_register | │
│           sales_register | capital_gains | other         │
│  If confidence < 0.9: flag for human classification     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              EXTRACTION (type-specific prompts)          │
│  vendor_bill: vendor_name, gstin, invoice_number, etc   │
│  bank_statement: date, narration, debit, credit, balance│
│  form_16: employer, gross_salary, deductions, TDS       │
│  notice: section, demand_amount, deadline, AY           │
│  trial_balance: ledger_name, debit, credit              │
│  deduction_register: deductee, PAN, section, TDS        │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              VALIDATION (Python rules, NOT AI)           │
│  GSTIN checksum, arithmetic, date validity, duplicate   │
│  PAN format, TDS rate, statutory limits                 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              CONFIDENCE DECISION                         │
│  All fields present + validation passes → 0.95+         │
│  1-2 fields null OR validation warning → 0.75           │
│  Multiple fields null OR validation fail → 0.50         │
│  If confidence < 0.85 → surface to human with original  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              STORE + PROCEED                             │
│  Update extracted_data in database                       │
│  Continue to next workflow step (matching, computation)  │
└─────────────────────────────────────────────────────────┘
```

---

## The Upload Component (Frontend)

### What the Accountant Sees

```
┌─────────────────────────────────────────────────────────┐
│  Upload Document                                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │                                                 │    │
│  │   📄 Drop files here or click to upload          │    │
│  │                                                 │    │
│  │   Supports: PDF, CSV, Excel, JPG, PNG           │    │
│  │   Max size: 20MB per file                       │    │
│  │                                                 │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  Or: 📱 Send via WhatsApp to +91 98XXX XXXXX           │
│                                                         │
│  Recent uploads:                                        │
│  ✅ Bank statement — HDFC — 23 Jun — 847 transactions  │
│  ✅ Vendor bill — Shree Traders — ₹18,450              │
│  ⏳ Form 16 — Acme Corp — processing...               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### What the Agent Does After Upload

1. **Store** → Supabase Storage (private bucket, pre-signed URLs)
2. **Classify** → Gemini Flash-Lite: "What type of document?"
3. **Extract** → Type-specific prompt (vendor bill fields, bank transactions, etc.)
4. **Validate** → Python rules engine (GSTIN, arithmetic, duplicates)
5. **Flag** → If confidence < 0.85, surface to human with original image
6. **Store result** → Update `documents.extracted_data` with structured JSON
7. **Proceed** → Continue to workflow step (matching, computation, filing)

---

## Connectors Needed Per Workflow

| Workflow | API Connectors | Playwright Connectors | Upload/Vision | Total |
|----------|---------------|----------------------|---------------|-------|
| **Vendor Bill** | Zoho Books | — | WhatsApp, PDF, Gemini Vision | 3 |
| **Bank Reconciliation** | Zoho Books | — (AA later) | PDF, CSV, Gemini Vision | 3 |
| **GSTR-3B** | Zoho Books | GSTN Portal | PDF, Gemini Vision | 3 |
| **GSTR-1** | Zoho Books, IRP | GSTN Portal | PDF, CSV, Gemini Vision | 4 |
| **ITR** | CAMS, Brokers | IT Portal | PDF, WhatsApp, Gemini Vision | 4 |
| **TDS** | Zoho Books | TRACES, IT Portal | PDF, CSV, Gemini Vision | 4 |
| **Payroll** | Zoho Books | EPFO, ESIC | CSV | 3 |
| **Tax Audit** | Zoho Books | IT Portal | PDF, Excel, Gemini Vision | 4 |
| **MCA** | — | MCA21 | PDF, Gemini Vision | 2 |
| **Notice Response** | — | IT Portal, GSTN, TRACES | WhatsApp, PDF, Gemini Vision | 4 |
| **TOTAL** | | | | **~12 unique connectors** |

---

## The 12 Unique Connectors (Not 32)

After mapping every workflow × input method, the actual unique connectors needed are:

| # | Connector | Type | Used By Workflows |
|---|-----------|------|-------------------|
| 1 | **Zoho Books** | API | All (accounting data) |
| 2 | **GSTN Portal** | Playwright | GSTR-3B, GSTR-1 |
| 3 | **IT Portal** | Playwright | ITR, TDS, Tax Audit |
| 4 | **TRACES** | Playwright | TDS |
| 5 | **MCA21** | Playwright | MCA filings |
| 6 | **EPFO** | Playwright | Payroll |
| 7 | **ESIC** | Playwright | Payroll |
| 8 | **WhatsApp** | API | Vendor Bill, Notice Response |
| 9 | **Gemini Vision** | API | All (document extraction) |
| 10 | **CAMS** | API | ITR (capital gains) |
| 11 | **Tally** | Bridge | Alternative to Zoho Books |
| 12 | **Account Aggregator** | API | Bank Reconciliation (Phase 2) |

**The "32 connectors" from earlier was inflated.** The real number is **12 unique connectors** that cover all 10 workflows.

---

## Build Order (Revised)

### Phase 1: MVP (Months 1-4)

| # | Connector | Why | Time |
|---|-----------|-----|------|
| 1 | **Zoho Books** | All workflows need accounting data | 1 week |
| 2 | **GSTN Portal** | GSTR-3B (most frequent) | 3 weeks |
| 3 | **WhatsApp** | Vendor bill processing | 1 week |
| 4 | **Gemini Vision** | Document extraction | ✅ Done |
| 5 | **Document Upload** | PDF/CSV upload UI + pipeline | 1 week |

### Phase 2: Growth (Months 5-8)

| # | Connector | Why | Time |
|---|-----------|-----|------|
| 6 | **IT Portal** | ITR filing | 2 weeks |
| 7 | **TRACES** | TDS returns | 2 weeks |
| 8 | **Tally** | Alternative to Zoho Books | 2 weeks |
| 9 | **CAMS** | Capital gains for ITR | 3 days |
| 10 | **EPFO** | Payroll | 1 week |

### Phase 3: Scale (Months 9-18)

| # | Connector | Why | Time |
|---|-----------|-----|------|
| 11 | **MCA21** | MCA filings | 2 weeks |
| 12 | **Account Aggregator** | Bank data (replaces PDF upload) | 2 weeks |
| 13 | **ESIC** | Payroll | 1 week |
| 14 | **GSTN GSP API** | Replace Playwright for GST | 2 weeks |

---

## What NOT to Do (Revised)

| Don't | Why |
|-------|-----|
| Don't build 32 connectors | You need 12. That's it. |
| Don't skip the upload flow | PDF upload is how 80% of accountants will give you data. |
| Don't require API connections for everything | PDF upload + Gemini Vision covers most cases. |
| Don't skip the document classifier | Agent must know what type of document it received. |
| Don't skip confidence scoring | Low-confidence extractions must surface to human. |
| Don't auto-commit without approval | `interrupt()` before `commit()`. Always. |

---

## The One Thing That Matters

**The upload flow is the MVP's secret weapon.**

You don't need API connections to everything on day one. You need:
1. Accountant uploads PDF/CSV/WhatsApp photo
2. Gemini Vision extracts data
3. Python rules validate
4. Agent processes (match, compute, draft)
5. Human approves
6. Agent commits

**This covers 90% of workflows without any portal automation.**

Portal automation (Playwright) is Phase 2 — when you need to file returns programmatically. But the upload → extract → process → approve flow works from day one.

**Go build it.**
