# 1 · Automation Scope Document — firmOS

## firmOS · Complete Automation Scope Document

**Version 1.0 · June 2026 · Founder-grade execution reference**

---

## Automation Philosophy

<aside>
💡

firmOS operates on one principle: **automate the mechanical, amplify the judgment.** The agent does all data retrieval, computation, reconciliation, and form preparation. The CA reviews the output and approves. Nothing commits to a government portal, accounting system, or bank without explicit human approval.

</aside>

Every financial workflow has two components:

- **Mechanical work** — data retrieval, computation, matching, form-filling. 80–90% of total time. Fully automatable.
- **Judgment work** — professional sign-off, exception handling, disclosures, legal decisions. 10–20% of time. Human-owned, always.

---

## Automation Levels

| Level | Description | Examples |
| --- | --- | --- |
| **L1 — Full Auto** | Agent completes 100%, human reviews in <30 seconds | Bank reconciliation, PAN validation, challan match |
| **L2 — Auto + Review** | Agent prepares complete draft, human approves | GSTR-3B, ITR-4, Payroll, MCA filings |
| **L3 — Auto + Edit** | Agent drafts 40 of 44 clauses, human fills gaps | Tax Audit 3CD, Form 15CA/15CB |
| **L4 — Agent Assists** | Agent surfaces data, human drives decision | Notice response, advisory, due diligence |

---

## Workflow 1: GSTR-3B Monthly Filing

**User goal:** File accurate GSTR-3B by the 20th of every month without manually reconciling 2B vs books.

**Trigger:** Automatic (calendar — 8 days before due date) or manual command.

**Inputs:**

- Sales ledger from accounting software
- Purchase ledger from accounting software
- Bank statement for the period

**Data sources:**

- GSTN API — GSTR-2B (auto-populated supplier invoices)
- Zoho Books API / Tally bridge (purchase and sales ledger)
- HDFC / ICICI bank via Account Aggregator (bank data)

**Agent responsibilities:**

- Fetch GSTR-2B from GSTN
- Read purchase ledger from accounting software
- Match each purchase invoice against 2B (PAN + invoice number + amount ±₹1)
- Flag mismatches: not in 2B, amount difference, GSTIN format error
- Defer ITC for mismatched invoices with follow-up list
- Compute output tax from sales ledger
- Compute eligible ITC (only 2B-confirmed invoices)
- Populate all GSTR-3B tables (3.1 to 5)
- Compute net payable and generate challan if payable > 0

**Human approval points:**

- Review mismatch list — confirm deferred ITC decisions
- Review final GSTR-3B draft
- Approve payment challan amount
- Final e-filing (DSC / EVC)

**Outputs:** GSTR-3B JSON + PDF draft · Mismatch report · Payment challan · ARN acknowledgement · Audit log entry

**Risk level:** 🔴 High — incorrect ITC attracts 24% interest + demand notices

**Audit requirements:** Log every data source read (timestamp, source, version) · Preserve original 2B download · Record human approval (user ID + timestamp) · Store final filed JSON · Immutable after filing

**Technical implementation path:**

- GSTN data: Browser automation (Playwright) as MVP → upgrade to GSP license Phase 2
- Books data: Zoho Books API (buy) / Tally XML bridge (build)
- Matching engine: Python rules-based (build, deterministic)
- Portal filing: Playwright browser automation (build)
- PDF generation: ReportLab (buy)

**Automation level: L2 · Time saved: 2.5 hrs → 5 min per client**

---

## Workflow 2: GSTR-1 Monthly Filing

**User goal:** File accurate outward supply details by the 11th of each month.

**Trigger:** Automatic calendar or manual command.

**Inputs:** Sales invoices from accounting software, e-invoice data from IRP, customer GSTIN list

**Data sources:** Accounting software API (sales register) · IRP API (e-invoice/IRN data) · GSTN API (GSTIN validation)

**Agent responsibilities:**

- Fetch all sales invoices for the period
- Classify: B2B (with GSTIN), B2C large (>₹2.5L), B2C small, exports, nil-rated, exempted
- Validate all customer GSTINs via GSTN API
- Validate HSN codes, invoice numbers, tax arithmetic
- Reconcile with IRP for e-invoice data
- Populate GSTR-1 tables (Table 4 B2B, Table 7 B2C, Table 6 exports)
- Cross-verify turnover against books

**Human approval points:** Review classification exceptions · Approve before submission · Handle nil-filing decision

**Risk level:** 🔴 High — GSTR-1 directly impacts buyer's ITC

**Technical path:** Accounting software API (buy) · GSTN GSP API (build) · Playwright fallback (build)

**Automation level: L2 · Time saved: 1.5 hrs → 3 min per client**

---

## Workflow 3: ITR Filing (All Types)

**User goal:** File accurate income tax return before due date for all client types.

**Trigger:** Annual calendar trigger (June–July) or client request via WhatsApp.

**Inputs:**

- Form 26AS + AIS (IT Portal)
- Form 16 (employer, PDF)
- Capital gains statements (broker / CAMS / NSDL)
- Bank interest certificates
- Business P&L (for ITR-3/4)
- Investment proofs for deductions (80C, 80D, 80CCD)

**Data sources:** Income Tax Portal (26AS, AIS via Playwright) · Account Aggregator (bank interest) · CAMS/NSDL API (mutual fund capital gains) · Broker APIs (Zerodha, Groww) · Accounting software (business income)

**Agent responsibilities:**

- Pull 26AS and AIS automatically
- Parse Form 16 PDF via Gemini Vision (structured extraction)
- Parse capital gains statements
- Classify all income sources with correct schedule
- Apply eligible deductions per relevant sections
- Compute tax under old regime vs new regime, recommend optimal
- Compute interest u/s 234B and 234C if advance tax was missed
- Populate ITR JSON per IT Department schema
- Generate draft for CA review

**Human approval points:**

- Regime selection (old vs new) in marginal cases — CA recommends, client decides
- Capital gains classification (STCG vs LTCG boundary cases)
- All Schedule FA (foreign assets) disclosures — mandatory CA review
- Review total tax liability before filing
- E-verification or physical signature by client

**Risk level:** 🔴 High — incorrect filing triggers notices

**Automation level: L2 · Time saved: 4 hrs → 10 min per client**

**Technical path:** IT Portal scraping via Playwright (build) · CAMS CAMSNet API (buy, ₹5/transaction) · Gemini Vision for Form 16 (buy) · Tax computation: deterministic Python (build, never AI) · ITR JSON per IT Dept schema (build)

---

## Workflow 4: TDS Return (24Q / 26Q)

**User goal:** File quarterly TDS return by 31 Jul / 31 Oct / 31 Jan / 31 May without manual FVU file preparation.

**Inputs:** Deduction register from accounting software · Challan deposit receipts (OLTAS) · Employee/deductee master with PANs

**Data sources:** Accounting software (deduction ledger) · TRACES API (challan verification) · IT Portal API (PAN validation)

**Agent responsibilities:**

- Compile all deductions for the quarter
- Validate all 12+ PANs via IT Portal API
- Match challans with deductions via TRACES
- Identify short deductions, late deposits
- Compute interest u/s 201A and late filing fee u/s 234E
- Generate FVU file in NSDL format (RPU-validated)
- Prepare covering letter for CA review

**Human approval points:** Review short deductions (CA decides correction approach) · High-value deductions >₹10L (manual review) · Filing confirmation

**Risk level:** 🔴 High — 234E: ₹200/day late filing fee · 201(1A): 1.5%/month interest

**Automation level: L2 · Time saved: 2.5 hrs → 10 min per return**

**Technical path:** FVU file generation per NSDL spec (build, Python) · TRACES API (build) · Playwright fallback for TRACES portal (build)

---

## Workflow 5: Tax Audit — Form 3CD

**User goal:** Complete Form 3CD tax audit for entities with turnover > ₹1 Cr.

**Trigger:** Annual (September–October), after accounts finalized.

**Inputs:** Finalized P&L and Balance Sheet · Trial balance · All ledgers (cash, purchase, sales) · Bank statements · Prior year 3CD

**Data sources:** Accounting software API (trial balance) · TRACES (TDS clause 34) · Internal computation engine

**Agent responsibilities:**

- Extract trial balance from accounting software
- Auto-populate automatable clauses (approx 30 of 44):
    - Clause 13: Method of accounting
    - Clause 14: Valuation of closing stock
    - Clause 15: Profit / turnover
    - Clause 17: Land and building purchases
    - Clause 21: Deductions claimed
    - Clause 26: Cash payments > ₹20,000 (Sec 40A)
    - Clause 27: Payments to specified persons
    - Clause 34: TDS compliance
    - Clause 36B: MSMED compliance
- Flag clauses requiring CA judgment (Clauses 16, 19, 30, 40)
- Generate draft 3CD in XML format per IT Dept schema
- Prepare observation list with evidence references

**Human approval points:**

- CA MUST review all 44 clauses — professional and legal responsibility
- All observations and disclosures — CA drafts and approves
- Form 3CB covering letter — CA's independent analysis
- CA's digital signature — mandatory for filing (cannot be automated)

**Risk level:** 🔴 Very High — CA's professional liability · Incorrect 3CD = penalty u/s 271B

**Automation level: L3 — agent prepares ~30/44 clauses, CA reviews and completes all 44**

**Technical path:** Trial balance via accounting software API (buy) · 3CD XML per IT Dept spec (build) · Clause mapping rules engine in Python (build) · IT Portal filing via Playwright (build)

---

## Workflow 6: Payroll Processing

**User goal:** Compute monthly salaries, deduct PF/ESI/TDS, generate payslips, transfer salaries.

**Trigger:** Monthly (25th–last working day)

**Inputs:** Employee master · Attendance data · Investment declarations (for TDS) · Previous month payroll

**Agent responsibilities:**

- Import attendance from HR system or uploaded CSV
- Compute gross salary (basic + HRA + allowances + overtime)
- Deduct PF: 12% employee + 13% employer (EPFO ECR format)
- Deduct ESI: 0.75% employee + 3.25% employer (salary < ₹21,000)
- Compute TDS on salary using projected annual income method
- Compute Professional Tax (state-specific slabs)
- Generate payslips (PDF)
- Generate EPFO ECR file, ESI return file
- Generate bank NEFT transfer file
- Prepare Form 16 Part B year-end data

**Human approval points:** New employee additions / deletions · Salary revisions · Variable components (bonus, commission) · Final approval before NEFT transfer · Annual Form 16 review per employee

**Risk level:** 🟡 Medium — payroll errors affect employee trust + statutory compliance

**Automation level: L2 · Time saved: 2 hrs → 5 min per company**

**Technical path:** EPFO ECR format (build, Python) · Bank NEFT format (build per bank spec) · Payslip PDF (build, ReportLab) · ESI return (build, Playwright for ESIC portal)

---

## Workflow 7: MCA / ROC Annual Filings

**User goal:** File MGT-7 (annual return) and AOC-4 (financial statements) before deadlines.

**Trigger:** Annual calendar — 29 October (AOC-4), 29 November (MGT-7)

**Inputs:** Company master from MCA21 · Audited financial statements · Shareholder register · Director details with DINs

**Agent responsibilities:**

- Fetch company data from MCA21 API
- Extract financial data from audited statements
- Populate MGT-7 (shareholding pattern, directors, AGM date, registered office)
- Populate AOC-4 (P&L, BS, notes, auditor report attachment)
- Validate all DINs and director KYC status on MCA portal
- Generate XML for portal filing

**Human approval points:** Directors review and approve MGT-7 · Professional sign-off (CS or CA) · DSC signing — mandatory, cannot be automated · Board resolution references

**Risk level:** 🔴 High — late filing: ₹100/day per form additional fees

**Automation level: L2 · Time saved: 6 hrs → 30 min per company**

---

## Workflow 8: Bank Reconciliation

**User goal:** Match all bank transactions against ledger entries. Identify unreconciled items.

**Trigger:** Monthly (1st of month) or on-demand.

**Inputs:** Bank statement (PDF upload, or Account Aggregator data) · Bank ledger from accounting software

**Agent responsibilities:**

- Parse bank statement: PDF → structured via Gemini Vision, or AA API data
- Fetch bank ledger entries from accounting software
- Match transactions: amount exact + date ±3 days + narration fuzzy match (RapidFuzz)
- Auto-clear matched entries
- Flag: unmatched bank entries, unmatched book entries, duplicates, round-number anomalies
- Compute closing balance difference
- Prepare BRS (Bank Reconciliation Statement) PDF

**Human approval points:** Review unmatched items · Approve posting of new ledger entries · Sign off on final BRS

**Risk level:** 🟢 Low — internal document, no government portal submission

**Automation level: L1 — 95%+ match rate achievable · Time saved: 3 hrs → 5 min**

---

## Workflow 9: Notice Response

**User goal:** Respond to income tax / GST / TDS notices accurately and on time.

**Trigger:** Client uploads notice PDF / CA receives on portal.

**Inputs:** Notice PDF · Client's filed returns · Supporting documents

**Agent responsibilities:**

- Parse and classify notice: 143(1), 148, 245, 139(9), GSTN mismatch, TRACES demand
- Extract key data: demand amount, assessment year, section, response deadline
- Pull relevant filed data and compute if demand is correct or incorrectly raised
- Draft factual response letter with supporting calculation
- Prepare list of supporting documents required

**Human approval points:** CA reviews ALL notice responses — no exceptions · Legal strategy is always human-owned · CA signs all correspondence · Client approval for any payment or settlement

**Risk level:** 🔴 Very High — incorrect response can escalate to litigation, penalty, prosecution

**Automation level: L4 — agent drafts, CA drives completely**

---

## Automated vs Human-Owned Summary

| Workflow | Automation % | Human Role | Automation Level |
| --- | --- | --- | --- |
| Bank Reconciliation | 95% | Review exceptions, approve BRS | L1 |
| GSTR-3B Filing | 85% | Review mismatches, approve, file | L2 |
| GSTR-1 Filing | 80% | Review exceptions, approve | L2 |
| TDS Return | 80% | Review short deductions, approve | L2 |
| ITR-1 / ITR-4 | 80% | Review tax, approve, e-verify | L2 |
| Payroll Processing | 75% | Approve variable pay, bank transfer | L2 |
| MCA Filings | 70% | DSC signing, director approval | L2 |
| Tax Audit 3CD | 40% | Review all 44 clauses, CA certifies | L3 |
| Notice Response | 20% | CA reviews, decides strategy, signs | L4 |
| Statutory Audit | 15% | Entire audit is CA's professional work | L4 |

---

## Final Operating Model

<aside>
⚡

**firmOS is a human-supervised automation platform.** The agent handles 80% of the work mechanically. The CA handles 20% — the part that requires professional judgment and legal responsibility.

</aside>

**The operating cycle for every workflow:**

1. **Agent collects** — fetches data from portals, APIs, accounting software, documents
2. **Agent computes** — runs deterministic logic (tax slabs, matching, form population)
3. **Agent proposes** — creates a complete draft with confidence score and flagged exceptions
4. **Human reviews** — CA sees the output in < 5 minutes on firmOS
5. **Human approves** — single keyboard shortcut `A` triggers commitment
6. **Agent commits** — submits to portal / posts to accounting software
7. **System records** — immutable audit log entry created for every action

**What firmOS never does without explicit human approval:**

- Submit to any government portal
- Post any journal entry to accounting software
- Transfer any money
- Send any correspondence to tax authorities

**Implementation recommendation:** Start with GSTR-3B + ITR-4 as the first two workflows. They cover the most clients, are the most repeatable, and have the clearest approval points. Perfect these before adding more. One workflow done to 99% accuracy is worth more than five done to 80%.