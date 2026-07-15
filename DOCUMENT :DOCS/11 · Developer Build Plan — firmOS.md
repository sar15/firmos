# 11 · Developer Build Plan — firmOS

## firmOS · How, What, Where, What Not To Do

**Version 1.0 · June 2026 · Developer execution guide**

---

## The App Flow (Complete)

### How a Workflow Executes End-to-End

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. TRIGGER                                                      │
│    Calendar (8 days before due date) OR Manual command           │
│    Example: "Run GSTR-3B for Acme Traders"                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 2. DATA COLLECTION                                               │
│    Agent fetches data from ALL available sources:                │
│    • API: Zoho Books (purchase register, sales register)        │
│    • Playwright: GSTN Portal (GSTR-2B download)                 │
│    • Upload: Bank statement PDF, vendor bill photos              │
│    • WhatsApp: Client sends documents                            │
│    Each source has its OWN connector module                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 3. DOCUMENT PROCESSING (if upload/WhatsApp)                      │
│    Gemini Vision extracts structured data from documents         │
│    Python rules validate (GSTIN, arithmetic, dates)              │
│    Confidence scoring (0.0 - 1.0)                                │
│    Low confidence (< 0.85) → flag for human review               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 4. MATCHING / RECONCILIATION                                     │
│    Agent matches data across sources:                            │
│    • Purchase invoices vs GSTR-2B (GSTIN + invoice + amount)    │
│    • Bank transactions vs books (amount + date + narration)     │
│    • Deductions vs challans (TDS matching)                      │
│    Deterministic Python engine — NOT AI                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 5. COMPUTATION                                                   │
│    Deterministic Python rules engine (100% test coverage):       │
│    • Tax slabs, surcharge, cess                                  │
│    • ITC eligibility, net payable                                │
│    • Interest u/s 234B, 234C                                     │
│    • FVU file generation                                         │
│    NEVER uses AI for computation                                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 6. DRAFT GENERATION                                              │
│    Agent creates complete draft:                                 │
│    • GSTR-3B JSON + PDF summary                                  │
│    • BRS with matched/unmatched items                            │
│    • ITR JSON with all schedules                                 │
│    • Confidence score per field                                  │
│    • Flags for items needing human attention                     │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 7. HUMAN APPROVAL (LangGraph interrupt)                          │
│    ActionProposal created in database                            │
│    CA notified: in-app + WhatsApp + email                        │
│    CA sees: complete draft + agent log + confidence scores       │
│    Decision: Approve (A) / Edit (E) / Reject (R)                │
│    Approval logged: user ID, timestamp, IP, exact output shown   │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 8. COMMIT                                                        │
│    Agent executes approved action:                               │
│    • Portal filing: Playwright submits to GSTN/IT Portal         │
│    • Ledger posting: Zoho Books API creates entries              │
│    • File generation: FVU, ECR, NEFT file                        │
│    Idempotency check before EVERY commit                         │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 9. AUDIT LOG                                                     │
│    Immutable entry written to audit_logs table:                  │
│    • timestamp, firm_id, client_id, user_id                      │
│    • action_type, workflow_type, description                     │
│    • input_snapshot (JSONB), output_snapshot (JSONB)             │
│    • confidence, ip_address, session_id                          │
│    REVOKE UPDATE/DELETE on audit_logs — forever                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────────┐
│ 10. CONFIRMATION                                                 │
│    CA notified: "GSTR-3B filed for Acme Traders. ARN: XXXXX"    │
│    Client notified (if applicable): WhatsApp confirmation        │
│    Compliance calendar updated: status = filed                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Connector Build Guide

### How to Build Each Connector

#### Connector 1: Zoho Books (1 Week)

**Where to build:**
```
firmos-backend/connectors/zoho_books/
├── __init__.py
├── server.py              # MCP server entry point
├── auth.py                # OAuth2 flow
├── client.py              # Typed API client
├── schemas.py             # Pydantic models
├── tools/
│   ├── fetch_purchase_register.py
│   ├── fetch_sales_register.py
│   ├── fetch_bank_ledger.py
│   └── post_purchase_entry.py
├── health.py              # Health check
└── config.py              # Configuration
```

**How to build:**

Day 1-2: OAuth2 flow
```python
# auth.py
import httpx

ZOHO_ACCOUNTS_URL = "https://accounts.zoho.in/oauth/v2/token"

async def get_access_token(refresh_token: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(ZOHO_ACCOUNTS_URL, data={
            "grant_type": "refresh_token",
            "client_id": os.environ["ZOHO_CLIENT_ID"],
            "client_secret": os.environ["ZOHO_CLIENT_SECRET"],
            "refresh_token": refresh_token,
        })
        return resp.json()["access_token"]
```

Day 3-4: Typed API client
```python
# client.py
class ZohoBooksClient:
    def __init__(self, access_token: str, org_id: str):
        self.client = httpx.AsyncClient(
            base_url="https://www.zohoapis.in/books/v3",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            timeout=30,
        )
        self.org_id = org_id
    
    async def get_purchases(self, period: str) -> list[Purchase]:
        resp = await self.client.get(
            f"/organizations/{self.org_id}/purchases",
            params={"date_start": period_start, "date_end": period_end}
        )
        return [Purchase(**p) for p in resp.json()["purchases"]]
```

Day 5-7: MCP tools + test

**What NOT to do:**
- ❌ Don't store refresh tokens in database — use encrypted vault
- ❌ Don't skip token refresh — Zoho tokens expire in 1 hour
- ❌ Don't ignore rate limits — 100 req/min, implement exponential backoff
- ❌ Don't use community SDK — use direct REST calls with httpx

**Open source reference:**
- httpx: `encode/httpx` (GitHub, MIT license)
- Pydantic: `pydantic/pydantic` (GitHub, MIT license)

---

#### Connector 2: GSTN Portal (3 Weeks)

**Where to build:**
```
firmos-backend/connectors/gstn/
├── __init__.py
├── server.py              # MCP server entry point
├── session_manager.py     # Login, cookie persistence, re-login
├── gstr2b_downloader.py   # Download GSTR-2B for period
├── gstr3b_filler.py       # Fill GSTR-3B tables
├── otp_handler.py         # Pause → notify CA → enter OTP → resume
├── submission.py          # Submit + capture ARN
├── anti_detection.py      # Human-like delays, stealth plugin
├── failure_capture.py     # Screenshot on error
├── selectors.py           # Portal UI selectors (config file)
└── config.py              # Configuration
```

**How to build:**

Day 1-2: Docker container + session management
```python
# session_manager.py
from playwright.async_api import async_playwright

class GSTNSession:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
    
    async def login(self, username: str, password: str) -> bool:
        self.browser = await async_playwright().start()
        self.context = await self.browser.new_context(
            storage_state="session.json" if os.path.exists("session.json") else None
        )
        self.page = await self.context.new_page()
        
        await self.page.goto("https://services.gst.gov.in/services/login")
        await self.page.fill("#username", username)
        await self.page.fill("#password", password)
        await self.page.click("#login_button")
        
        # Handle OTP if needed
        if await self.page.locator("#otp").is_visible():
            await self.handle_otp()
        
        # Save session
        await self.context.storage_state(path="session.json")
        return True
```

Day 3-4: GSTR-2B download
```python
# gstr2b_downloader.py
class GSTR2BDownloader:
    async def download(self, period: str) -> dict:
        await self.page.goto("https://services.gst.gov.in/services/search/returndashboard")
        await self.page.select_option("#return_period", period)
        await self.page.click("#gstr2b_download")
        
        # Wait for download
        async with self.page.expect_download() as download_info:
            await self.page.click("#download_button")
        download = await download_info.value
        
        # Parse downloaded file
        return self.parse_gstr2b(download.path)
```

Day 5-6: GSTR-3B form filling
```python
# gstr3b_filler.py
class GSTR3BFiller:
    async def fill_and_submit(self, data: GSTR3BData) -> FilingResult:
        await self.page.goto("https://services.gst.gov.in/services/search/returndashboard")
        await self.page.select_option("#return_period", data.period)
        await self.page.click("#gstr3b_prepare")
        
        # Fill Table 3.1 (Outward supplies)
        await self.page.fill("#table31_total_taxable", str(data.total_taxable))
        await self.page.fill("#table31_cgst", str(data.cgst))
        await self.page.fill("#table31_sgst", str(data.sgst))
        await self.page.fill("#table31_igst", str(data.igst))
        
        # Fill Table 4 (Eligible ITC)
        await self.page.fill("#table4_cgst", str(data.itc_cgst))
        await self.page.fill("#table4_sgst", str(data.itc_sgst))
        await self.page.fill("#table4_igst", str(data.itc_igst))
        
        # Submit
        await self.page.click("#submit_button")
        
        # Handle OTP
        await self.handle_otp()
        
        # Capture ARN
        arn = await self.page.locator("#arn").inner_text()
        return FilingResult(arn=arn, status="filed")
```

Day 7: Anti-detection + error handling
```python
# anti_detection.py
import asyncio
import random

async def human_delay():
    """Wait 1-3 seconds between actions to look human"""
    await asyncio.sleep(random.uniform(1.0, 3.0))

async def stealth_page(context):
    """Apply stealth patches to avoid bot detection"""
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    """)
```

**What NOT to do:**
- ❌ Don't hardcode selectors — use `selectors.py` config file (portal UI changes frequently)
- ❌ Don't skip idempotency check — always check if return is already filed before filling
- ❌ Don't run parallel sessions for same firm + portal — mutex per (firm_id, portal_name)
- ❌ Don't skip screenshot on failure — store in Supabase with 7-day TTL
- ❌ Don't ignore anti-bot detection — use `playwright-extra` stealth plugin

**Open source reference:**
- Playwright: `microsoft/playwright` (GitHub, 13k stars, Apache 2.0)
- Stealth plugin: `playwright-extra` + `puppeteer-extra-plugin-stealth`
- Browser automation pattern: `browser-use/browser-use` (GitHub, 57k stars)

---

#### Connector 3: WhatsApp Business (1 Week)

**Where to build:**
```
firmos-backend/connectors/whatsapp/
├── __init__.py
├── server.py              # MCP server entry point
├── webhook_handler.py     # Process incoming messages
├── message_sender.py      # Send messages
├── image_handler.py       # Process images (vendor bills, notices)
├── templates.py           # Predefined message templates
└── config.py              # Configuration
```

**How to build:**

Day 1-2: Webhook setup
```python
# webhook_handler.py
from fastapi import FastAPI, Request

app = FastAPI()

@app.post("/webhook/whatsapp")
async def handle_webhook(request: Request):
    data = await request.json()
    
    # Verify webhook (Meta requires this)
    if "hub.mode" in data:
        return verify_webhook(data)
    
    # Process incoming message
    message = data["entry"][0]["changes"][0]["value"]["messages"][0]
    
    if message["type"] == "image":
        # Client sent a photo (vendor bill, notice, etc.)
        await process_image(message)
    elif message["type"] == "text":
        # Client replied with text (approval, query)
        await process_text(message)
    
    return {"status": "ok"}
```

Day 3: Image processing
```python
# image_handler.py
from google.cloud import aiplatform

class WhatsAppImageProcessor:
    async def process(self, image_url: str, sender: str) -> DocumentResult:
        # 1. Download image from WhatsApp CDN
        image_bytes = await download_image(image_url)
        
        # 2. Store in Supabase Storage
        storage_path = f"whatsapp/{sender}/{timestamp}.jpg"
        await supabase.storage.from_("documents").upload(storage_path, image_bytes)
        
        # 3. Classify document type
        doc_type = await classify_document(image_bytes)
        
        # 4. Extract fields based on type
        if doc_type == "VENDOR_BILL":
            fields = await extract_vendor_bill(image_bytes)
        elif doc_type == "NOTICE":
            fields = await extract_notice(image_bytes)
        elif doc_type == "BANK_STATEMENT":
            fields = await extract_bank_statement(image_bytes)
        
        # 5. Create action proposal
        proposal = await create_proposal(doc_type, fields, sender)
        
        # 6. Notify CA
        await notify_ca(proposal)
        
        return DocumentResult(proposal_id=proposal.id)
```

Day 4-5: Message templates + send
```python
# templates.py
TEMPLATES = {
    "bill_received": "Got it. Processing your bill from {vendor_name}...",
    "bill_approved": "✓ Bill from {vendor_name} ₹{amount} recorded in your books.",
    "approval_request": "New bill from {vendor_name} ₹{amount} ready for approval.",
    "notice_received": "Got notice from {portal}. Processing...",
    "filing_complete": "✓ {workflow} filed for {client}. ARN: {arn}",
}
```

**What NOT to do:**
- ❌ Don't store WhatsApp credentials in code — use env vars
- ❌ Don't skip webhook verification — Meta requires it
- ❌ Don't send messages too fast — rate limit is 80 msgs/second
- ❌ Don't process images synchronously — use background queue

**Open source reference:**
- WhatsApp Business API: Meta Cloud API (official docs)
- Image processing: Google Cloud Vision API or Gemini Vision

---

#### Connector 4: Gemini Vision (Already Done)

**What it does:**
- Classifies document types (vendor bill, bank statement, Form 16, notice)
- Extracts structured data from PDFs and images
- Returns confidence scores per field

**How it works:**
```python
# Already built — here's the pattern
from vertexai.generative_models import GenerativeModel

model = GenerativeModel("gemini-3.1-flash-lite")

async def extract_vendor_bill(image_bytes: bytes) -> ExtractionResult:
    prompt = """Extract these fields from this vendor invoice:
    - vendor_name (string)
    - vendor_gstin (string, 15-char alphanumeric)
    - invoice_number (string)
    - invoice_date (string, DD/MM/YYYY)
    - taxable_amount (number)
    - cgst (number)
    - sgst (number)
    - igst (number, 0 if not present)
    - total_amount (number)
    If any field is unclear, return null. Never guess. Return JSON only."""
    
    response = await model.generate_content_async([
        prompt,
        Part.from_data(data=image_bytes, mime_type="image/jpeg")
    ])
    
    return ExtractionResult.model_validate_json(response.text)
```

---

#### Connector 5: Document Upload Pipeline (1 Week)

**Where to build:**
```
firmos-backend/connectors/document_upload/
├── __init__.py
├── server.py              # MCP server entry point
├── upload_handler.py      # Handle file uploads
├── classifier.py          # Classify document type
├── extractor.py           # Extract structured data
├── validator.py           # Validate extracted data
├── confidence.py          # Score confidence
└── config.py              # Configuration
```

**How to build:**

Day 1-2: Upload handler
```python
# upload_handler.py
from fastapi import UploadFile, File

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    client_id: str = Form(...),
    workflow_type: str = Form(...),
):
    # 1. Store file
    content = await file.read()
    storage_path = f"uploads/{client_id}/{workflow_type}/{file.filename}"
    await supabase.storage.from_("documents").upload(storage_path, content)
    
    # 2. Classify
    doc_type = await classify_document(content, file.filename)
    
    # 3. Extract
    extraction = await extract_fields(content, doc_type)
    
    # 4. Validate
    validation = await validate_extraction(extraction)
    
    # 5. Score confidence
    confidence = await score_confidence(extraction, validation)
    
    # 6. Store result
    document = await store_document(client_id, doc_type, extraction, confidence)
    
    # 7. If low confidence, flag for human
    if confidence < 0.85:
        await flag_for_human_review(document)
    
    return {"document_id": document.id, "confidence": confidence}
```

Day 3-4: Classifier + extractor
```python
# classifier.py
DOCUMENT_TYPES = [
    "VENDOR_BILL", "BANK_STATEMENT", "FORM_16", "NOTICE",
    "TRIAL_BALANCE", "DEDUCTION_REGISTER", "SALES_REGISTER",
    "CAPITAL_GAINS", "OTHER"
]

async def classify_document(content: bytes, filename: str) -> str:
    # Use filename hints first
    if "bank" in filename.lower() or "statement" in filename.lower():
        return "BANK_STATEMENT"
    if "form 16" in filename.lower() or "form16" in filename.lower():
        return "FORM_16"
    
    # Use Gemini Vision for classification
    prompt = f"Classify this financial document. Options: {DOCUMENT_TYPES}. Return JSON: {{type, confidence}}"
    response = await gemini.classify(content, prompt)
    return response.type
```

Day 5-7: Validator + confidence scorer + test
```python
# validator.py
class DocumentValidator:
    def validate_vendor_bill(self, extraction: dict) -> ValidationResult:
        errors = []
        
        # GSTIN checksum
        if extraction.get("vendor_gstin"):
            if not self.validate_gstin_checksum(extraction["vendor_gstin"]):
                errors.append("GSTIN checksum invalid")
        
        # Arithmetic
        taxable = extraction.get("taxable_amount", 0)
        cgst = extraction.get("cgst", 0)
        sgst = extraction.get("sgst", 0)
        igst = extraction.get("igst", 0)
        total = extraction.get("total_amount", 0)
        
        computed_total = taxable + cgst + sgst + igst
        if abs(computed_total - total) > 1:
            errors.append(f"Arithmetic mismatch: {computed_total} ≠ {total}")
        
        # Date validity
        if extraction.get("invoice_date"):
            date = parse_date(extraction["invoice_date"])
            if date > datetime.now():
                errors.append("Future-dated invoice")
            if date < datetime.now() - timedelta(days=730):
                errors.append("Invoice older than 2 years")
        
        return ValidationResult(errors=errors, valid=len(errors) == 0)
```

**What NOT to do:**
- ❌ Don't guess extraction fields — if unclear, return null
- ❌ Don't skip validation — every extraction must be validated
- ❌ Don't auto-commit low-confidence extractions — surface to human
- ❌ Don't store raw files without backup — keep originals forever

---

## Where to Build (Project Structure)

```
firmos-backend/
├── app/
│   ├── main.py                    # FastAPI entry point
│   ├── config.py                  # Environment variables
│   ├── database.py                # Supabase connection
│   ├── auth.py                    # JWT validation
│   │
│   ├── connectors/                # ALL CONNECTORS LIVE HERE
│   │   ├── __init__.py            # Registry auto-registration
│   │   ├── base.py                # BaseConnector protocol
│   │   ├── registry.py            # ConnectorRegistry
│   │   │
│   │   ├── zoho_books/            # Connector 1
│   │   │   ├── __init__.py
│   │   │   ├── server.py          # MCP server
│   │   │   ├── auth.py            # OAuth2
│   │   │   ├── client.py          # API client
│   │   │   ├── schemas.py         # Pydantic models
│   │   │   ├── tools/             # MCP tools
│   │   │   ├── health.py          # Health check
│   │   │   └── config.py          # Configuration
│   │   │
│   │   ├── gstn/                  # Connector 2
│   │   │   ├── __init__.py
│   │   │   ├── server.py
│   │   │   ├── session_manager.py
│   │   │   ├── gstr2b_downloader.py
│   │   │   ├── gstr3b_filler.py
│   │   │   ├── otp_handler.py
│   │   │   ├── submission.py
│   │   │   ├── anti_detection.py
│   │   │   ├── failure_capture.py
│   │   │   ├── selectors.py
│   │   │   └── config.py
│   │   │
│   │   ├── whatsapp/              # Connector 3
│   │   │   ├── __init__.py
│   │   │   ├── server.py
│   │   │   ├── webhook_handler.py
│   │   │   ├── message_sender.py
│   │   │   ├── image_handler.py
│   │   │   ├── templates.py
│   │   │   └── config.py
│   │   │
│   │   ├── gemini_vision/         # Connector 4 (already done)
│   │   │   └── ...
│   │   │
│   │   └── document_upload/       # Connector 5
│   │       ├── __init__.py
│   │       ├── server.py
│   │       ├── upload_handler.py
│   │       ├── classifier.py
│   │       ├── extractor.py
│   │       ├── validator.py
│   │       ├── confidence.py
│   │       └── config.py
│   │
│   ├── workflows/                 # LangGraph workflows
│   │   ├── __init__.py
│   │   ├── gstr3b.py              # GSTR-3B workflow
│   │   ├── gstr1.py               # GSTR-1 workflow
│   │   ├── itr.py                 # ITR workflow
│   │   ├── tds.py                 # TDS workflow
│   │   ├── payroll.py             # Payroll workflow
│   │   ├── bank_recon.py          # Bank reconciliation
│   │   ├── vendor_bill.py         # Vendor bill processing
│   │   ├── tax_audit.py           # Tax audit 3CD
│   │   ├── mca.py                 # MCA filings
│   │   └── notice.py              # Notice response
│   │
│   ├── engines/                   # Deterministic computation
│   │   ├── __init__.py
│   │   ├── tax.py                 # Income tax computation
│   │   ├── gst.py                 # GST computation
│   │   ├── tds.py                 # TDS computation
│   │   ├── matcher.py             # Invoice matching
│   │   ├── reconciler.py          # Bank reconciliation
│   │   └── validators.py          # GSTIN, PAN, arithmetic
│   │
│   ├── api/                       # FastAPI routes
│   │   ├── __init__.py
│   │   ├── clients.py             # Client CRUD
│   │   ├── workflows.py           # Workflow triggers
│   │   ├── approvals.py           # Decision inbox
│   │   ├── documents.py           # Document upload
│   │   ├── audit.py               # Audit log (read-only)
│   │   └── connectors.py          # Connector management
│   │
│   └── models/                    # Database models
│       ├── __init__.py
│       ├── firms.py
│       ├── clients.py
│       ├── action_proposals.py
│       ├── documents.py
│       ├── audit_logs.py
│       └── compliance_calendar.py
│
├── connectors/                    # MCP servers (separate process)
│   ├── zoho_books/
│   ├── gstn/
│   ├── whatsapp/
│   └── ...
│
├── tests/
│   ├── test_connectors/
│   ├── test_workflows/
│   ├── test_engines/
│   └── test_api/
│
├── alembic/                       # Database migrations
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## What NOT to Do (Developer Rules)

### Code Rules

| Rule | Why |
|------|-----|
| **Never use AI for tax computation** | Tax is deterministic Python. AI explains, never computes. |
| **Never skip `interrupt()` before commit** | Human approval is non-negotiable. |
| **Never hardcode portal selectors** | Government portals change UI. Use config files. |
| **Never skip idempotency check** | Never double-file. Check before every commit. |
| **Never store credentials in plaintext** | AES-256-GCM encryption. Key in env vars, not DB. |
| **Never skip audit logging** | Every action logged. Immutable forever. |
| **Never auto-commit low-confidence outputs** | Confidence < 0.85 → surface to human. |
| **Never use `any` type** | Pydantic schemas with `z.infer` or `BaseModel`. |

### Architecture Rules

| Rule | Why |
|------|-----|
| **Don't build all connectors at once** | Build 5 for MVP, prove the model. |
| **Don't skip the document upload flow** | PDF upload covers 90% of workflows without portal automation. |
| **Don't require API connections for everything** | Upload + Gemini Vision works without any API. |
| **Don't skip the health check** | Every connector must have a health check endpoint. |
| **Don't skip rate limiting** | Every external API call must be rate-limited. |
| **Don't skip error handling** | Every error either retries and succeeds, or surfaces to human. |

### Deployment Rules

| Rule | Why |
|------|-----|
| **Don't deploy to production without tests** | 100% test coverage on tax computation engine. |
| **Don't skip database migrations** | Alembic for every schema change. |
| **Don't skip environment variable validation** | Pydantic Settings validates all env vars on startup. |
| **Don't skip Sentry error tracking** | Every error tracked, every failure alerted. |

---

## Open Source References

### Core Framework

| What | Project | Stars | License | Use For |
|------|---------|-------|---------|---------|
| **MCP** | `modelcontextprotocol/servers` | 87.7k | MIT | Connector protocol |
| **LangGraph** | `langchain-ai/langgraph` | 35.9k | MIT | Agent workflows |
| **Playwright** | `microsoft/playwright` | 13k | Apache 2.0 | Portal automation |
| **FastAPI** | `tiangolo/fastapi` | 80k+ | MIT | API framework |
| **Pydantic** | `pydantic/pydantic` | 20k+ | MIT | Data validation |
| **httpx** | `encode/httpx` | 13k+ | BSD | HTTP client |

### Document Processing

| What | Project | Stars | License | Use For |
|------|---------|-------|---------|---------|
| **Gemini Vision** | Google Cloud | — | — | PDF/image extraction |
| **PyMuPDF** | `pymupdf/PyMuPDF` | 12k+ | AGPL | PDF parsing |
| **RapidFuzz** | `maxbachmann/RapidFuzz` | 2k+ | MIT | Fuzzy text matching |
| **pandas** | `pandas-dev/pandas` | 42k+ | BSD | CSV/Excel processing |

### Authentication & Security

| What | Project | Stars | License | Use For |
|------|---------|-------|---------|---------|
| **cryptography** | `pyca/cryptography` | 6k+ | Apache 2.0 | AES-256-GCM encryption |
| **python-jose** | `mpdavis/python-jose` | 1.8k | MIT | JWT handling |

### Monitoring

| What | Project | Stars | License | Use For |
|------|---------|-------|---------|---------|
| **Sentry** | `getsentry/sentry-python` | 4k+ | MIT | Error tracking |
| **Langfuse** | `langfuse/langfuse` | 7k+ | MIT | LLM observability |
| **structlog** | `hynek/structlog` | 1.8k | Apache 2.0 | Structured logging |

### PDF Generation

| What | Project | Stars | License | Use For |
|------|---------|-------|---------|---------|
| **ReportLab** | `ReportLab/reportlab` | 4k+ | BSD | PDF generation |

---

## Testing Strategy

### What to Test

| Component | Test Type | Coverage Target |
|-----------|-----------|-----------------|
| **Tax computation engine** | Unit tests | 100% — against CBDT sample computations |
| **GST computation** | Unit tests | 100% — every slab boundary |
| **TDS computation** | Unit tests | 100% — every section rate |
| **Invoice matching** | Unit + integration | 95% — exact, near, fuzzy match |
| **Bank reconciliation** | Unit + integration | 95% — all match phases |
| **Document extraction** | Integration | 90% — sample documents |
| **Portal automation** | Integration | Manual — against staging portal |
| **API routes** | Integration | 100% — all endpoints |

### Test Commands

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test suite
pytest tests/test_engines/test_tax.py -v

# Run tax computation against CBDT samples
pytest tests/test_engines/test_tax_cbdt_samples.py -v
```

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...

# Redis
REDIS_URL=redis://...

# Google Cloud
GOOGLE_CLOUD_PROJECT=firmos-prod
VERTEX_LOCATION=asia-south1

# Zoho Books
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REDIRECT_URI=https://firmos.app/auth/zoho/callback

# GSTN Portal
GSTN_USERNAME=...
GSTN_PASSWORD=...  # encrypted

# WhatsApp
WHATSAPP_TOKEN=...
WHATSAPP_PHONE_ID=...

# Encryption
ENCRYPTION_KEY=<32-byte-key>

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
```

---

## Docker Compose (Development)

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres

  worker:
    build: .
    command: python -m app.worker
    environment:
      - DATABASE_URL=postgresql://...
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres

  portal:
    build: ./connectors/gstn
    ports:
      - "8001:8001"
    environment:
      - ENCRYPTION_KEY=...

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: firmos
      POSTGRES_PASSWORD: dev
    ports:
      - "5432:5432"
```

---

## The One Thing That Matters

**Build the upload → extract → process → approve flow first.**

This covers 90% of workflows without any portal automation. Portal automation (Playwright) is Phase 2.

**Go build it.**
