# 5 · Technical Requirements Document (TRD) — firmOS

## firmOS · Technical Requirements Document

**Version 1.0 · June 2026 · Decisive. Opinionated. Build this.**

<aside>
⚙️

Every recommendation in this document is a final choice, not a menu of options. When facing a build/buy decision, we default to **buy** if cost < ₹4L/year and the vendor has >99.9% reliability. We default to **build** when the logic is core to firmOS's correctness or competitive advantage (tax computation, reconciliation, portal automation). We do not over-engineer for scale we don't yet have.

</aside>

---

## 1. System Architecture

### Pattern: Modular Monolith First

**Decision:** One FastAPI application, well-separated modules. Not microservices. Not serverless functions per workflow.

**Rationale:** A 2-person engineering team cannot operate microservices reliably. A modular monolith delivers all the code organization benefits without operational complexity. We split into separate services only when there is a specific, measured bottleneck — not preemptively.

**Exception:** Portal automation (Playwright) runs as a separate Docker container from Day 1. Chromium is too heavy to bundle with the API service, and portal automation needs isolated sessions.

### Architecture Diagram

```
┌───────────────────────────────────────────────────────────────┐
│                      CLIENT LAYER                           │
│   Next.js 15 (Vercel CDN)      WhatsApp Bot (Railway)       │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTPS / REST
┌──────────────────────────────┤ 
│          API SERVICE          │
│   FastAPI 0.115 / Python 3.12  │
│   Railway · Gunicorn+Uvicorn   │
│   /auth /clients /workflows    │
│   /approvals /docs /audit      │
└──────┬──────────┬─────────┬─────┘
       │          │          │
┌─────┴──┐  ┌────┴───┐  ┌───┴─────┐
│ Supabase  │  │ LangGraph │  │ Vertex AI  │
│ Postgres  │  │ Worker    │  │ Gemini 3.1 │
│ Storage   │  │ Railway   │  │ asia-south1│
│ Auth      │  │ + Upstash │  └──────────┘
│ ap-south-1│  │   Redis   │
└──────────┘  └─────┴───┘
                   │
┌───────────────┴──────────────┐
│  Portal Automation Service      │
│  Docker + Playwright             │
│  Railway · Chromium headless      │
│  GSTN · IT Portal · TRACES        │
│  MCA21 · EPFO · ESIC              │
└──────────────────────────────┘
```

---

## 2. Services

### 2.1 API Service (FastAPI)

**Repository:** `firmos-api/`

**Module structure:**

```
app/
  auth/           — JWT validation, user sessions
  clients/        — CRUD for firms and clients
  workflows/      — trigger, monitor, cancel workflows
  approvals/      — inbox management, decision recording
  documents/      — upload handler, extraction trigger
  audit/          — read-only audit log access
  integrations/
    zoho.py       — Zoho Books API wrapper
    whatsapp.py   — Meta Cloud API webhook + send
    gemini.py     — Vertex AI / Gemini API wrapper
  engines/
    tax.py        — income tax computation (deterministic)
    gst.py        — GST computation and reconciliation
    matcher.py    — invoice and bank transaction matching
    validators.py — GSTIN, PAN, arithmetic validators
```

**Framework:** FastAPI 0.115+ with Pydantic v2 (strict mode for all inputs)

**Server:** Uvicorn workers behind Gunicorn. Start with 4 workers.

**Railway config:** 1 service, 512MB RAM (upgrade to 1GB at 100+ concurrent workflows)

### 2.2 LangGraph Workflow Worker

**Repository:** `firmos-worker/` (separate Railway service)

**Why separate:** Long-running workflows (5–10 minutes) should not block the API service. Worker pulls jobs from Redis queue, executes LangGraph state machines, updates Supabase.

**Architecture:**

```python
# Every workflow follows this pattern
from langgraph.graph import StateGraph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

class GSTRWorkflowState(TypedDict):
    firm_id: str
    client_id: str
    period: str
    raw_data: dict       # fetched from portals and APIs
    extracted: dict      # structured data
    computed: dict       # tax computation results  
    draft: dict          # human-readable output
    confidence: float
    flags: list[dict]
    proposal_id: str
    status: str
    error: str | None

# Build the graph
graph = StateGraph(GSTRWorkflowState)
graph.add_node("collect", collect_data)
graph.add_node("compute", compute_gstr3b)
graph.add_node("draft", generate_draft)
graph.add_node("await_approval", await_human_approval)  # interrupt here
graph.add_node("commit", commit_to_portal)
graph.add_node("record", write_audit_log)

# interrupt() pauses execution until CA approves
async def await_human_approval(state):
    interrupt({"proposal_id": state["proposal_id"], "type": "GSTR_3B"})
    return {"status": "waiting_approval"}
```

**Checkpoint:** `AsyncPostgresSaver` writes workflow state to Supabase Postgres. Workflow survives worker restarts.

**Redis:** Upstash Redis for job queue. Job format: `{workflow_id, firm_id, client_id, type, payload}`

### 2.3 Portal Automation Service

**Repository:** `firmos-portal/` (Docker container on Railway)

**Dockerfile:**

```docker
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium --with-deps
COPY . .
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

**Portal handler pattern:**

```python
class GSTNPortalHandler:
    def __init__(self, credentials: PortalCredentials):
        self.creds = credentials
        self.browser: Browser | None = None
        self.page: Page | None = None
    
    async def login(self) -> bool:
        """Login with retry. Returns True on success."""
        
    async def download_gstr2b(self, period: str) -> GSTRData:
        """Download and parse GSTR-2B for given period."""
    
    async def file_gstr3b(self, gstr3b_data: GSTR3BData) -> FilingResult:
        """File GSTR-3B. Returns ARN on success."""
```

**Session management:** Each firm gets a separate browser context (isolated cookies, storage). Sessions persisted to Redis with TTL 4 hours. Re-login only when session expires.

**Anti-detection:** `playwright-extra` with stealth plugin. Human-like delays (1–3 seconds between actions). No parallel sessions for same firm + same portal.

**Failure capture:** Screenshot on every error. Stored in Supabase Storage with 7-day TTL. Used for debugging and support.

---

## 3. Database Architecture

### Primary: Supabase PostgreSQL 15 (ap-south-1)

**Multi-tenancy via Row Level Security:**

```sql
-- Application database role (used by all app connections)
CREATE ROLE app_user NOLOGIN;

-- Force RLS on every table — cannot be bypassed by app_user
ALTER TABLE clients FORCE ROW LEVEL SECURITY;
ALTER TABLE action_proposals FORCE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE compliance_calendar FORCE ROW LEVEL SECURITY;

-- Isolation policy — set at connection time by FastAPI
CREATE POLICY firm_isolation ON clients
  USING (firm_id = current_setting('app.current_firm_id', true)::uuid);

-- FastAPI sets this on every request
async def get_db_connection(user: AuthUser):
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute(f"SET app.current_firm_id = '{user.firm_id}'")
    await conn.execute("SET ROLE app_user")
    return conn
```

**Critical: Never use Supabase `service_role` key in application code.** Service role bypasses RLS. Use `anon` key + authenticated JWT for all app operations.

**Audit log immutability:**

```sql
-- Revoke at database level — cannot be overridden by application
REVOKE UPDATE ON audit_logs FROM app_user;
REVOKE DELETE ON audit_logs FROM app_user;
REVOKE UPDATE ON audit_logs FROM authenticated;
REVOKE DELETE ON audit_logs FROM authenticated;
REVOKE UPDATE ON audit_logs FROM service_role;
REVOKE DELETE ON audit_logs FROM service_role;
-- INSERT only. From now until the company exists.
```

**Indexes (critical for performance):**

```sql
CREATE INDEX idx_action_proposals_firm_status 
  ON action_proposals(firm_id, status) WHERE status = 'pending';
CREATE INDEX idx_audit_logs_firm_created 
  ON audit_logs(firm_id, created_at DESC);
CREATE INDEX idx_compliance_calendar_due 
  ON compliance_calendar(firm_id, due_date) WHERE status = 'pending';
CREATE INDEX idx_clients_firm 
  ON clients(firm_id) WHERE status = 'active';
```

### Document Storage: Supabase Storage

- Bucket: `documents` with per-firm path prefix: `{firm_id}/{client_id}/{doc_type}/{filename}`
- Private bucket: access via pre-signed URLs (15-minute expiry)
- Original files retained indefinitely (legal requirement)
- Extracted data stored in Postgres `documents.extracted_data` (JSONB)
- Never delete originals. Archive instead.

### Queue: Upstash Redis

- Serverless Redis, generous free tier (10,000 commands/day free)
- Job queue: `LPUSH jobs {payload}` / `BRPOP jobs 30` (blocking pop)
- Dead letter queue: after 3 failures, move to `jobs_failed`
- Session cache: portal sessions with TTL 4 hours
- Rate limiting: per-firm API call counts

---

## 4. Agent Architecture — LangGraph

### Standard Workflow State Schema

```python
class WorkflowState(TypedDict):
    # Identity
    workflow_id: str
    firm_id: str
    client_id: str
    workflow_type: str
    period: str
    
    # Execution
    step: str                    # current step name
    retry_count: int             # retries for current step
    started_at: str
    
    # Data
    collected_data: dict         # raw data from all sources
    extracted_data: dict         # structured after processing
    computed: dict               # final computation results
    draft: dict                  # human-readable proposal
    confidence: float            # 0.0 to 1.0
    flags: list[dict]            # items needing CA attention
    
    # Approval
    proposal_id: str
    status: str                  # collecting|computing|waiting|approved|committed|failed
    decision: str | None         # approve|reject|edit
    decision_note: str | None
    
    # Output
    commit_result: dict | None   # portal/API response
    error: str | None
```

### Standard Node Sequence

```
collect_data → validate_inputs → compute → generate_draft → [interrupt] → commit → record
```

### Error Handling per Node

```python
async def with_retry(fn, state, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await fn(state)
        except PortalTimeoutError:
            if attempt == max_retries - 1:
                return {"status": "failed", "error": "Portal timeout after 3 attempts"}
            await asyncio.sleep(2 ** attempt * 10)  # 10s, 20s, 40s backoff
        except ExtractionFailedError as e:
            return {"status": "needs_human", "error": str(e)}
```

### Human Interrupt Pattern

```python
# In the 'await_approval' node:
async def await_approval(state: WorkflowState):
    # This creates the action_proposal in Supabase
    proposal = await create_action_proposal(state)
    await notify_ca(state.firm_id, proposal.id)
    
    # interrupt() pauses LangGraph execution here
    # Execution resumes only when CA approves via API
    interrupt({"proposal_id": proposal.id})
    
    # After resume: state.decision is set by API
    return {"proposal_id": proposal.id}

# CA approval endpoint resumes the graph:
async def approve_proposal(proposal_id: str, user: AuthUser):
    proposal = await get_proposal(proposal_id)
    await record_decision(proposal_id, "approve", user)
    
    # Resume LangGraph thread
    await graph.aupdate_state(
        config={"thread_id": proposal.langgraph_thread_id},
        values={"decision": "approve", "decided_by": user.id}
    )
    await graph.ainvoke(None, config={...})  # resume from interrupt
```

---

## 5. Document Processing Pipeline

### Pipeline for Every Uploaded Document

```
1. RECEIVE
   WhatsApp webhook / web upload → store in Supabase Storage
   Generate: document_id, storage_path
   Write: documents record with status='processing'

2. CLASSIFY
   Gemini Flash-Lite prompt: "Classify this financial document.
   Options: vendor_bill | bank_statement | form_16 | gstr_notice |
   income_tax_notice | other. Return JSON: {type, confidence}"
   If confidence < 0.9: flag for human classification

3. EXTRACT (type-specific prompts)
   
   For vendor_bill:
   "Extract exactly these fields from this vendor invoice:
   vendor_name (string), vendor_gstin (string, format: 15-char alphanumeric),
   invoice_number (string), invoice_date (string, DD/MM/YYYY),
   taxable_amount (number, no currency symbol), cgst (number),
   sgst (number), igst (number, 0 if not present), total_amount (number).
   If any field is unclear or absent, return null for that field.
   Never guess. Return JSON only."

4. VALIDATE (Python rules, not AI)
   GSTIN: checksum algorithm (modular 97)
   Arithmetic: taxable + cgst + sgst + igst = total ± Re.1
   Date: valid format, not future, not >2 years old
   Invoice number: not blank
   Confidence: if any field is null, reduce confidence score

5. CONFIDENCE DECISION
   All fields present + validation passes: confidence = 0.95+
   1-2 fields null OR validation warning: confidence = 0.75
   Multiple fields null OR validation fail: confidence = 0.50
   
   If confidence < 0.85: surface to human with original image
   and pre-filled form showing extracted values for correction

6. STORE
   Update documents.extracted_data with structured JSON
   Update documents.extraction_confidence
   Write audit_log: action_type=DOCUMENT_EXTRACTED
```

### Gemini API Integration

```python
from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, Part

class GeminiExtractor:
    def __init__(self):
        aiplatform.init(project=settings.GCP_PROJECT, location="asia-south1")
        self.model = GenerativeModel("gemini-1.5-flash-002")
    
    async def extract_vendor_bill(self, image_bytes: bytes) -> ExtractionResult:
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
        response = await self.model.generate_content_async(
            [VENDOR_BILL_PROMPT, image_part],
            generation_config={"response_mime_type": "application/json"}
        )
        return ExtractionResult.model_validate_json(response.text)
```

---

## 6. Tax Computation Engine

**Rule: Tax computation is always deterministic Python. AI never computes tax.**

```python
class IncomeTaxFY2526:
    """Finance Act 2025 — FY 2025-26 (AY 2026-27)"""
    
    OLD_REGIME_SLABS = [
        (250_000, 0.00),
        (500_000, 0.05),
        (1_000_000, 0.20),
        (float('inf'), 0.30)
    ]
    
    NEW_REGIME_SLABS = [
        (300_000, 0.00),
        (700_000, 0.05),
        (1_000_000, 0.10),
        (1_200_000, 0.15),
        (1_500_000, 0.20),
        (float('inf'), 0.30)
    ]
    
    def compute(self, income: TaxableIncome, regime: str) -> TaxResult:
        slabs = self.OLD_REGIME_SLABS if regime == 'old' else self.NEW_REGIME_SLABS
        tax = self._apply_slabs(income.total_taxable, slabs)
        surcharge = self._compute_surcharge(income.total_taxable, tax)
        cess = (tax + surcharge) * Decimal('0.04')
        total = tax + surcharge + cess
        return TaxResult(basic_tax=tax, surcharge=surcharge, cess=cess, total=total)
    
    def _apply_slabs(self, income: Decimal, slabs: list) -> Decimal:
        tax = Decimal('0')
        prev_limit = Decimal('0')
        for limit, rate in slabs:
            if income <= prev_limit:
                break
            taxable_in_slab = min(income, Decimal(str(limit))) - prev_limit
            tax += taxable_in_slab * Decimal(str(rate))
            prev_limit = Decimal(str(limit))
        return tax
```

**Testing requirement:** 100% test coverage against CBDT published sample computations. Test every slab boundary, marginal relief, surcharge threshold. Run these tests on every deploy.

---

## 7. Authentication & Authorization

### Authentication: Supabase Auth

- Email + OTP (passwordless, preferred for CA users — no password to forget or leak)
- WhatsApp OTP for mobile access
- JWT: 15-minute access token, 30-day refresh token
- Tokens stored in httpOnly cookies (not localStorage — prevents XSS theft)

### Authorization: Permission Check at API Layer

```python
from functools import wraps

def require_permission(permission: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, user: AuthUser, **kwargs):
            if not user.has_permission(permission):
                raise HTTPException(403, f"Permission denied: {permission}")
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator

@router.post("/approvals/{id}/approve")
@require_permission("approvals:portal_submit")
async def approve_for_filing(id: str, user: CurrentUser):
    # Only owner and manager reach here
    ...
```

**Permission matrix:**

```python
PERMISSIONS = {
    "owner": ["*"],  # all permissions
    "manager": [
        "clients:read", "clients:write",
        "workflows:run", "workflows:read",
        "approvals:read", "approvals:approve",
        "approvals:portal_submit",  # can approve portal filings
        "audit:read", "audit:export"
    ],
    "article_clerk": [
        "clients:read",
        "workflows:run", "workflows:read",
        "approvals:read",  # can see but NOT approve
        "audit:read"
    ],
    "view_only": ["clients:read", "workflows:read", "audit:read"]
}
```

---

## 8. Audit System

### Schema (append-only, forever)

```sql
CREATE TABLE audit_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    firm_id UUID NOT NULL,
    client_id UUID,
    user_id UUID NOT NULL,
    user_name TEXT NOT NULL,
    user_role TEXT NOT NULL,
    action_type TEXT NOT NULL CHECK (action_type IN (
        'DATA_READ', 'DOCUMENT_UPLOADED', 'DOCUMENT_EXTRACTED',
        'WORKFLOW_STARTED', 'STEP_COMPLETED', 'STEP_FAILED',
        'HUMAN_APPROVED', 'HUMAN_REJECTED', 'HUMAN_EDITED',
        'PORTAL_SUBMITTED', 'PORTAL_FAILED', 'PORTAL_RETRIED',
        'LEDGER_POSTED', 'LEDGER_FAILED',
        'AUDIT_LOG_EXPORTED', 'PORTAL_CREDENTIALS_UPDATED'
    )),
    workflow_type TEXT,
    workflow_id UUID,
    description TEXT NOT NULL,
    input_snapshot JSONB,
    output_snapshot JSONB,
    confidence DECIMAL(3,2),
    ip_address INET,
    session_id TEXT,
    metadata JSONB  -- additional context per action type
);

-- These grants are NEVER overridden. Ever.
REVOKE UPDATE ON audit_logs FROM ALL;
REVOKE DELETE ON audit_logs FROM ALL;
REVOKE TRUNCATE ON audit_logs FROM ALL;
```

### Writing Audit Logs

```python
async def audit(conn, **kwargs):
    """Write an audit log entry. Call this from every significant action."""
    await conn.execute("""
        INSERT INTO audit_logs 
        (firm_id, client_id, user_id, user_name, user_role, action_type,
         workflow_type, description, input_snapshot, output_snapshot, 
         confidence, ip_address, session_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
    """, kwargs['firm_id'], kwargs.get('client_id'), kwargs['user_id'], ...)
```

### Audit Export (PDF)

When a CA exports their audit trail:

1. Fetch all entries for the specified filter
2. Generate PDF: firm name, date range, filter applied, entry table
3. Compute SHA-256 hash of the raw JSON data
4. Include hash on last page: "Data integrity hash: abc123..."
5. Store export event itself as an audit log entry (action_type = AUDIT_LOG_EXPORTED)

---

## 9. Deployment Architecture

### Services and Hosting

| Service | Hosting | Config | Monthly |
| --- | --- | --- | --- |
| Next.js frontend | Vercel Pro | Edge CDN, auto-deploy on push | $20 |
| FastAPI API | Railway Starter | 1 service, 512MB RAM | $15 |
| LangGraph worker | Railway Starter | 1 service, 512MB RAM | $15 |
| Portal automation | Railway Starter | Docker, 1GB RAM (Chromium) | $20 |
| PostgreSQL | Supabase Pro | ap-south-1, 8GB storage | $25 |
| Redis queue | Upstash | Serverless, 10K cmds/day free | $0 |
| **Total** |  |  | **$95** |

### Environment Variables — Zero Secrets in Code

```
# Railway environment variables (encrypted at rest)
DATABASE_URL=postgresql://...
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...  # NOT service_role
REDIS_URL=redis://...
GOOGLE_CLOUD_PROJECT=firmos-prod
VERTEX_LOCATION=asia-south1
WHATSAPP_TOKEN=EAAx...
PORTAL_SERVICE_URL=https://firmos-portal.railway.app
ENCRYPTION_KEY=<32-byte-key-from-secrets-manager>
```

### CI/CD

- **Frontend:** Vercel auto-deploys on `git push` to `main`
- **Backend:** Railway auto-deploys on `git push` to `main`
- **Tests:** GitHub Actions runs test suite on every PR
- **Migrations:** `alembic upgrade head` runs on every backend deploy
- **Rollback:** Railway preserves last 3 deploys, one-click rollback

### Environments

- `main` branch → production
- `develop` branch → staging (Railway staging environment)
- Feature branches → preview deployments (Vercel)

---

## 10. Security Model

### Credential Storage

Portal credentials (GSTN password, IT Portal password) are the most sensitive data in firmOS. A breach exposes client tax data.

```python
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, base64

class CredentialVault:
    def __init__(self, key: bytes):
        # 32-byte key from environment variable (never from DB)
        self.aesgcm = AESGCM(key)
    
    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)  # 96-bit nonce
        ct = self.aesgcm.encrypt(nonce, plaintext.encode(), None)
        return base64.b64encode(nonce + ct).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        data = base64.b64decode(ciphertext)
        nonce, ct = data[:12], data[12:]
        return self.aesgcm.decrypt(nonce, ct, None).decode()
```

- Encryption key: stored in Railway environment variables, never in database
- Key rotation: quarterly, with migration script
- Decryption: only in portal automation service, never in frontend, never logged

### API Security

- Rate limiting: `slowapi` — 100 req/min per firm, 10 req/min for portal automation endpoints
- Input validation: Pydantic v2 strict mode on all request bodies
- SQL injection: SQLAlchemy parameterized queries + asyncpg parameters only
- CORS: whitelist only firmOS domain
- HTTPS: enforced at Vercel and Railway level
- Headers: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security`

### Portal Security

- Separate browser context per firm (no cross-contamination)
- Portal sessions stored in Redis with firm-specific keys
- Screenshot on failure: stored in Supabase with 7-day auto-delete policy
- No parallel sessions: mutex per (firm_id, portal_name) to prevent duplicate submissions

---

## 11. Monitoring & Error Handling

### Monitoring Stack (all free/cheap tier initially)

| Need | Tool | Cost | Setup |
| --- | --- | --- | --- |
| Error tracking | Sentry (free: 5K errors/month) | $0 | `pip install sentry-sdk` |
| Uptime monitoring | Better Uptime free tier | $0 | 10 monitors |
| LLM call logging | Langfuse (free: 100K events/month) | $0 | Track token usage, latency, accuracy |
| Database metrics | Supabase built-in | $0 | Query performance, connection pool |
| Application logs | Railway built-in + structured JSON | $0 | `structlog` library |

### Error Categories and Handling

```python
class ErrorCategory(Enum):
    PORTAL_DOWN = "portal_down"           # Retry with backoff
    PORTAL_CHANGED = "portal_changed"     # Alert engineering, pause workflow
    EXTRACTION_FAILED = "extraction_failed"  # Escalate to human
    COMPUTATION_ERROR = "computation_error"  # Critical: log + alert, never commit
    APPROVAL_TIMEOUT = "approval_timeout"    # Escalate after 48h
    COMMIT_FAILED = "commit_failed"          # Critical: notify immediately
    RATE_LIMITED = "rate_limited"            # Queue for retry
```

**Golden rule:** No silent failures. Every error either:

1. Retries and succeeds, OR
2. Surfaces to a human with clear explanation and next action

**Idempotency for portal submissions:**

```python
async def safe_file_gstr3b(client_id, period, data):
    # Check if already filed before touching portal
    existing = await check_gstn_filing_status(client_id, period)
    if existing.is_filed:
        return FilingResult(status="already_filed", arn=existing.arn)
    
    # Unique key prevents duplicate execution
    idempotency_key = f"GSTR3B:{client_id}:{period}"
    if await redis.get(idempotency_key):
        raise DuplicateSubmissionError("Filing already in progress")
    
    await redis.setex(idempotency_key, 300, "in_progress")  # 5-min lock
    try:
        result = await portal.file_gstr3b(data)
        return result
    finally:
        await redis.delete(idempotency_key)
```

---

## 12. Scalability Path

### Phase 1: MVP (0–50 CA firms) — Current architecture handles this comfortably

No changes needed. Free/starter tiers on all services.

### Phase 2: Growth (50–1,000 CA firms)

- Supabase: upgrade to Large instance ($299/month)
- Railway: scale API and worker to 2-4 instances each
- Add read replica for reporting queries (Supabase built-in)
- Add CDN for generated PDFs (Cloudflare R2, free 10GB/month)
- Redis: upgrade to Upstash Pro for higher throughput
- Portal automation: add 2 more Playwright worker instances

### Phase 3: Scale (1,000+ CA firms)

- Consider migrating from LangGraph to [Temporal.io](http://Temporal.io) for production-grade workflow orchestration
- GSP license for direct GSTN API (eliminates Playwright for GST workflows entirely)
- Account Aggregator integration (eliminates manual bank statement upload)
- Add Celery + Redis for bulk workflows (file 500 GSTR-3Bs simultaneously)
- Database sharding if needed (Supabase supports this with PgBouncer)
- Dedicated Playwright worker pools per portal type

**What does NOT change with scale:**

- PostgreSQL + RLS multi-tenancy: designed to scale to millions of rows
- LangGraph interrupt pattern: same code works at 1 firm or 10,000 firms
- Audit log append-only: Postgres handles 100M+ rows with proper indexes
- Tax computation engine: pure Python, stateless, infinitely scalable

---

## 13. Open-Source Libraries — Complete Reference

| Purpose | Library | Version | License |
| --- | --- | --- | --- |
| Web framework | `fastapi` | 0.115+ | MIT |
| Data validation | `pydantic` | v2.x | MIT |
| Async database | `asyncpg` | 0.29+ | Apache 2.0 |
| ORM (optional) | `sqlalchemy` | 2.x async | MIT |
| Agent workflows | `langgraph` | 1.x | MIT |
| Browser automation | `playwright` | 1.44+ | Apache 2.0 |
| AI SDK | `google-cloud-aiplatform` | 1.x | Apache 2.0 |
| Text matching | `rapidfuzz` | 3.x | MIT |
| PDF generation | `reportlab` | 4.x | BSD |
| PDF parsing | `pymupdf` (fitz) | 1.24+ | AGPL |
| Data processing | `pandas` | 2.x | BSD |
| Cryptography | `cryptography` | 42.x | Apache 2.0 / BSD |
| Rate limiting | `slowapi` | 0.1.x | MIT |
| Task queue | `arq` or `celery` | latest | MIT |
| Logging | `structlog` | 24.x | MIT |
| Error tracking | `sentry-sdk` | 2.x | MIT |
| Testing | `pytest`  • `pytest-asyncio` | latest | MIT |
| HTTP client | `httpx` | 0.27+ | BSD |
| Environment | `pydantic-settings` | 2.x | MIT |

<aside>
✅

**Final implementation recommendation:** Start with the simplest possible implementation of each workflow. Use Playwright before GSP API. Use PDF upload before Account Aggregator. Use manual bank statement before bank API. The integration complexity can be added later when the core workflow is proven. The business logic (tax computation, reconciliation, matching) must be correct from day one — invest in testing this thoroughly. The portal automation can be brittle early on — build excellent error handling and escalation to human before perfect reliability.

</aside>