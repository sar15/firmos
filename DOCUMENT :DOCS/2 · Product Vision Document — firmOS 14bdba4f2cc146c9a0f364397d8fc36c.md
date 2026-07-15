# 2 · Product Vision Document — firmOS

## firmOS · Product Vision Document

**Version 1.0 · June 2026 · Founder-grade**

---

## 1. The Problem

India has 130,000 practicing CAs, 300,000+ accountants, and 90 million registered GST entities. Every month, they collectively perform:

- 2.6 million+ GST return filings
- 850,000+ TDS returns per quarter
- 50 million+ ITR filings per year
- 65,000+ tax audits per year

**Every single piece of this work is done manually.** Logging into portals. Downloading files. Reconciling spreadsheets. Filling forms. Copy-pasting between Tally and a government website.

The same CA who studied for 5 years to understand complex tax law spends 70% of their day doing data entry work that a machine should do.

**The three core problems firmOS solves:**

**Problem 1: Repetitive mechanical work destroys professional leverage**

A CA filing GSTR-3B for 40 clients manually spends 2 hours per client per month = 80 hours/month on one return type alone. Same logic, same portals, same data. Perfectly automatable. Instead, they spend that time on high-value advisory that clients would pay more for.

**Problem 2: Portal fragmentation creates coordination hell**

GSTN · IT Portal · TRACES · MCA21 · EPFO · ESIC · 29 state PT portals. Each requires separate login, handles files differently, and goes down at inconvenient times. A single client's full compliance requires 8+ portal logins. firmOS consolidates all of this into one command.

**Problem 3: Human fatigue in repetitive work creates preventable errors**

Manual reconciliation errors cause ₹6,300 crore+ in ITC mismatches and demand notices annually. A CA working on their 35th GSTR-3B of the month will make errors that the first one wouldn't. firmOS's matching engine is consistent at client #1 and client #500.

---

## 2. Why Now — 2026

Four infrastructure conditions now exist that didn't exist in 2022:

**1. Account Aggregator (AA) is live at scale**

RBI's AA framework gives programmatic, consent-based access to bank data, insurance, mutual fund, and credit data. The data retrieval problem is solved.

**2. LLMs can process Indian financial documents reliably**

Gemini 3.1 Flash processes Form 16, bank statements, balance sheets, and government portal responses with >95% extraction accuracy at ₹0.02 per document. Document processing is solved and affordable.

**3. Browser automation of government portals is feasible and maintainable**

Playwright-based automation reliably handles GSTN, Income Tax Portal, TRACES, MCA21. The tooling has matured enough to build production-grade automation.

**4. India's compliance burden is increasing, not decreasing**

GST 2.0, new TDS sections (194R, 194S), stricter MCA requirements, MSMED compliance, DPDP Act — the CA's workload grows every Budget. Automation is no longer a nice-to-have. It is survival infrastructure for CA practices.

---

## 3. Category Definition

firmOS creates a new category: **Agentic Finance OS.**

This is distinct from every existing category:

| Category | What it does | firmOS difference |
| --- | --- | --- |
| Accounting software (Tally, Zoho) | Records transactions | firmOS executes workflows |
| Compliance tools (ClearTax) | Helps humans fill forms | firmOS prepares and files |
| Banks (HDFC, Mercury) | Moves money | firmOS manages what surrounds money |
| BI tools (Zoho Analytics) | Shows dashboards | firmOS makes decisions |
| Audit tools (Coraa) | Automates audit procedures | firmOS covers all financial work |

**Category name: Financial Work Operating System**

**The Cursor analogy:** Just as Cursor changed software development from "a developer writing code" to "a developer approving AI-written code," firmOS changes finance from "a CA filling forms" to "a CA approving agent-prepared filings." The professional's role doesn't diminish — it elevates. They spend time on judgment, not mechanics.

---

## 4. Vision Statement

<aside>
🎯

**firmOS is the operating system for Indian financial professionals** — where every repetitive financial workflow is automated, every decision is surfaced for human approval, and every action is permanently auditable. A solo CA runs a 200-client practice without hiring more staff. A business owner never logs into a government portal again. An individual taxpayer files their ITR in 3 minutes.

</aside>

---

## 5. Principles

**1. Automate the mechanical, amplify the judgment**

Every agent action is mechanical — data retrieval, computation, matching, form filling. Every human action is a decision — approve, reject, disclose, advise. We never blur this line. The agent never makes a judgment call. The human never does data entry.

**2. Trust is the product**

firmOS's deliverable is not a filed return. It is the certainty that the filing is accurate, the trail is clear, and the CA is protected. We optimize for trust above speed, above features, above growth. A single trust failure in Indian finance is catastrophic — penalties, notices, client loss, professional reputation. We build as if every action will be scrutinized by a tax officer.

**3. Nothing commits without a human**

No portal submission, no ledger entry, no bank transfer happens without explicit human approval. This is not a product feature. It is an architectural guarantee built into the workflow engine. `interrupt()` before `commit()`. Always.

**4. India-first, India-specific**

We are not a global tool adapted for India. firmOS understands GSTIN checksum validation, Form 3CD clause 26, Section 40A(3), EPFO ECR format, TRACES FVU specification, MCA21 XML schema — natively. Every compliance rule, every portal quirk, every government portal maintenance schedule is our domain knowledge.

**5. One place for all financial work**

A CA should never leave firmOS to do compliance work. Every portal, every return type, every workflow — one command, one screen. The mental overhead of context-switching between 8 portals is eliminated.

**6. Decisions over documents**

The CA receives a decision to approve, not a form to fill. "Approve GSTR-3B for Acme Traders — ₹41,600 payable, 1 ITC deferred" — not "here is a spreadsheet of 47 invoices to match."

**7. Calm, not anxious**

firmOS communicates like a trusted senior colleague — one clear priority at a time, no notification storms, no red alerts for routine tasks. A tax filing tool should reduce professional anxiety, not create it.

---

## 6. Competitive Positioning

| Dimension | ClearTax | Zoho Books | Tally | Coraa | **firmOS** |
| --- | --- | --- | --- | --- | --- |
| Core job | Help file returns | Record transactions | Record transactions | Statutory audit | Execute all financial workflows |
| Automation depth | Form-fill assistance | None | None | Audit procedures | End-to-end agentic execution |
| Portal coverage | 2 portals | None | None | Internal only | 8+ portals |
| Human role | Fills forms | Records data | Records data | Reviews working papers | Approves decisions |
| CA time saved | ~30% | 0% | 0% | ~30% | **70–80%** |
| India-specific depth | High | Medium | High | High | **Maximum** |
| Target market | All sizes | SMB | SMB | Large CA firms | **Solo to mid-size CA firms** |

**Positioning statement:** *"firmOS does the work. You approve."*

**Why we win against ClearTax:** ClearTax helps you fill forms faster. firmOS fills the forms for you. The category is different — ClearTax is a faster pencil, firmOS is a different kind of work entirely.

---

## 7. Long-term Moat

**Moat 1: Audit trail as proprietary dataset (compounding)**

Every firmOS action is logged with full context — which data was read, what was computed, what the CA approved, what was filed, what notices followed. Over time, this creates the most comprehensive dataset of Indian financial compliance patterns in existence. This data enables pattern detection that no competitor can replicate: "entities with >20% cash purchase ratio in Maharashtra get Clause 26 scrutiny in tax audits 73% of the time." Impossible to build without years of real filing data.

**Moat 2: Multi-client intelligence (network effect within a firm)**

A CA using firmOS across 100 clients develops cross-client pattern recognition embedded in the system. "Glow Pack Industries has a history of filing GSTR-1 late — defer their ITC automatically." "Acme Traders always has cash expenses in Q4 — pre-flag for Clause 26." This firm-level intelligence is non-transferable and compounds over time.

**Moat 3: Integration depth (engineering moat)**

The hardest part of building firmOS is not the AI — it is the integration work: GSTN API + GSP license, Account Aggregator consent flows, TRACES FVU format, MCA21 XML schema, EPFO ECR format, 29 state PT portals, Tally XML bridge, bank NEFT formats. Each integration takes 2–6 weeks to build and test in production. After 3 years, this is a 300+ week engineering moat that any competitor must rebuild from scratch.

---

## 8. Trust Architecture

Trust is built through four non-negotiable layers:

**Layer 1: Process trust**

- Nothing commits without approval
- Every approval is logged with user ID, timestamp, IP address
- Full decision audit trail exportable in one click
- Immutable logs — no deletion, no editing, ever

**Layer 2: Data trust**

- All data encrypted at rest (AES-256-GCM) and in transit (TLS 1.3)
- Supabase Mumbai instance (ap-south-1) — DPDP compliance, no cross-border data transfer
- Portal credentials encrypted at application layer before reaching database
- No client data used for model training (Vertex AI paid tier guarantee)

**Layer 3: Accuracy trust**

- Tax computation is a deterministic Python rules engine — never AI
- Every calculation shows its working (input values + formula + result)
- Every matched invoice shows the source data
- AI confidence score shown for every extraction — low confidence triggers human review
- Every computation cross-checked against statutory limits

**Layer 4: Auditability trust**

- Every action (read, compute, approve, submit) in permanent audit log
- Log exportable as signed PDF for any date range
- CA can produce complete compliance history for any client in 60 seconds
- Suitable for income tax scrutiny, GST audit, or ICAI peer review

---

## 9. AI Strategy

**Primary model:** Gemini 3.1 Flash-Lite (Vertex AI, asia-south1)

**Escalation model:** Gemini 3.0 Flash (for complex document reasoning)

**Why Gemini 3.1 Flash-Lite:**

- Vision capability — processes Form 16, bank statements, balance sheets as images
- 1M context window — entire year's financial statements in one call
- asia-south1 deployment — DPDP-compliant, lowest latency from India
- $0.25/M input tokens — most affordable vision-capable model
- Vertex AI paid tier — no training on client data (contractual guarantee)

**AI usage boundaries — what AI does and does not do:**

| AI Does | AI Does Not |
| --- | --- |
| Extract data from PDF documents | Compute final tax liability |
| Classify document types | Make filing decisions |
| Explain computed results in plain language | Determine GST classification of goods |
| Summarize mismatches | Determine legal interpretation |
| Draft response letters | Submit to government portals |
| Suggest deductions based on extracted data | Handle digital signatures |

**Tax computation rule:** Tax calculation is always a deterministic Python rules engine with 100% test coverage against CBDT sample computations. AI explains the output. AI never computes it.

**Escalation logic:** AI confidence < 0.85 on any extraction → surface original document to human with pre-filled form for correction. Never commit low-confidence outputs automatically.

---

## 10. What firmOS Is / Is Not

| firmOS IS | firmOS IS NOT |
| --- | --- |
| An agentic financial workflow executor | A chatbot or AI assistant |
| A CA's work operating system | An accounting or ERP system |
| A compliance automation platform | A financial advisory product |
| An approval and audit system | A document management system |
| India-specific compliance infrastructure | A global tool adapted for India |
| A human-in-the-loop system | A fully autonomous financial agent |
| Precise, calm, professional | Gamified, consumer-y, dashboard-heavy |
| The Cursor for Indian finance | The Tally replacement |

---

## 11. Three-Year Product Roadmap

### Year 1 — 2026: Prove the Model

**Theme: The fastest CA compliance platform in India**

- MVP: Vendor bill processing + GSTR-3B + GSTR-1 + ITR-4 + Bank Reconciliation
- 3 pilot CA firms → 15 paying firms by year-end
- 50 to 300 clients total
- 90%+ time reduction on covered workflows
- Zero human-error-caused incidents
- **Target: ₹50L ARR by December 2026**

### Year 2 — 2027: Expand Coverage

**Theme: All compliance, one platform**

- Add: TDS returns · Tax Audit 3CD · Payroll + PF/ESI · MCA annual filings · Advance tax · GSTR-9/9C
- GSP license for direct GSTN API (no Playwright dependency for GST)
- Account Aggregator integration (bank data via consent)
- CAMS API for capital gains
- 100+ CA firms, 2,000+ clients
- **Target: ₹3 Cr ARR by December 2027**

### Year 3 — 2028: Intelligence Layer

**Theme: CA's decision intelligence platform**

- Add: Notice response intelligence · Multi-entity consolidated compliance · Direct bank integrations · Mobile approval app · CA network benchmarking
- Coraa competitor: full statutory audit working papers
- ICAI partnership for CPE credit integration
- 500+ CA firms, 15,000+ clients
- **Target: ₹15 Cr ARR by December 2028**

<aside>
⚠️

**Implementation recommendation:** Do not start Year 2 workflows until Year 1 workflows are genuinely excellent. A CA who gets a single GSTR-3B wrong will never trust the system again. Depth beats breadth at every stage. One perfectly automated workflow earns more trust than five mediocre ones.

</aside>