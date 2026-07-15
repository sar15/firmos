# 9 · Connector/Plugin Implementation Plan — firmOS

## firmOS · Phase-by-Phase Build Plan (June 2026)

**Version 1.0 · June 2026 · Research-backed, execution-ready**

---

## The Architecture Decision

### What We're Building: MCP-First Connector System

**Decision:** Build connectors as MCP (Model Context Protocol) servers.

**Why MCP:**
- Open standard (87.7k GitHub stars, 11.1k forks)
- Supported by Claude, ChatGPT, Cursor, VS Code, and your own LangGraph agent
- One connector works everywhere — no per-AI-tool integration
- Tool discovery, execution, and auth are standardized
- Python SDK available (`modelcontextprotocol`)

**Reference:** github.com/modelcontextprotocol/servers (4,115 commits, actively maintained)

### The Three Layers

```
┌─────────────────────────────────────────────────┐
│           FRONTEND (Next.js 16)                 │
│  Connectors UI → status, auth, config           │
└──────────────────────┬──────────────────────────┘
                       │ API calls
┌──────────────────────▼──────────────────────────┐
│           CONNECTOR LAYER (FastAPI + MCP)        │
│  Each connector = MCP server with:              │
│  • Tools (functions the agent can call)          │
│  • Resources (data the agent can read)           │
│  • Auth handler (OAuth, credentials, consent)    │
│  • Health checker (ping, reconnect)              │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           EXTERNAL SERVICES                      │
│  Zoho Books · GSTN · IT Portal · WhatsApp · etc │
└─────────────────────────────────────────────────┘
```

---

## Phase 1: MVP (Months 1-4) — 8 Connectors

### Build Order (Research-Backed)

| Priority | Connector | Why First | Open Source Reference | Build Time |
|----------|-----------|-----------|----------------------|------------|
| 1 | **Supabase** | Already done | `@supabase/supabase-js` | ✅ Done |
| 2 | **Vertex AI (Gemini)** | Already done | `google-cloud-aiplatform` | ✅ Done |
| 3 | **LangGraph** | Already done | `langchain-ai/langgraph` (35.9k stars) | ✅ Done |
| 4 | **Redis** | Already done | `upstash/redis-python` | ✅ Done |
| 5 | **Zoho Books** | First accounting connector | Zoho Books API v3 (REST, OAuth2) | 1 week |
| 6 | **GSTN Portal** | Most-used government portal | Playwright + stealth plugin | 3 weeks |
| 7 | **WhatsApp Business** | Client communication channel | Meta Cloud API (webhook) | 1 week |
| 8 | **Playwright Runtime** | Portal automation container | `microsoft/playwright` (13k stars) | 1 week |

### Connector 5: Zoho Books (1 Week)

**API:** REST (JSON) · OAuth2 · Rate limit: 100 req/min

**Open Source Reference:**
- Zoho Books API v3: `www.zoho.com/books/api/v3/introduction/`
- Python SDK: `zohocrm-python-sdk` (community)
- OAuth2 flow: Standard authorization code grant

**Build Steps:**
```
Day 1-2: OAuth2 flow (register app → auth URL → callback → token exchange → refresh)
Day 3-4: API client (typed, rate-limited, error handling)
Day 5: Purchase register fetch (GET /api/v3/purchases)
Day 6: Sales register fetch (GET /api/v3/invoices)
Day 7: Test with real Zoho Books org
```

**Key Endpoints:**
```
GET  /api/v3/purchases          → Purchase register
GET  /api/v3/invoices           → Sales register
GET  /api/v3/banktransactions   → Bank ledger
POST /api/v3/purchases          → Create purchase entry
GET  /api/v3/organizations      → Health check
```

**What NOT to do:**
- ❌ Don't store refresh tokens in database — use encrypted vault
- ❌ Don't skip token refresh — Zoho tokens expire in 1 hour
- ❌ Don't ignore rate limits — 100 req/min, implement backoff

### Connector 6: GSTN Portal (3 Weeks)

**Approach:** Playwright browser automation (no public API initially)

**Open Source Reference:**
- Playwright: `microsoft/playwright` (13k stars, Apache 2.0)
- Stealth plugin: `playwright-extra` + `puppeteer-extra-plugin-stealth`
- Session management: Redis with TTL

**Build Steps:**
```
Week 1:
  Day 1-2: Docker container setup (Playwright + Chromium)
  Day 3-4: Session management (login, cookie persistence, re-login)
  Day 5: GSTR-2B download (navigate → select period → download)

Week 2:
  Day 1-2: GSTR-3B form filling (navigate → fill tables → submit)
  Day 3: OTP handling (pause → notify CA → enter OTP → resume)
  Day 4: Idempotency check (before filing, check if already filed)
  Day 5: Screenshot on failure (capture error state for debugging)

Week 3:
  Day 1-2: Anti-detection (human-like delays, stealth plugin)
  Day 3: Error handling (portal down → retry → escalate)
  Day 4: Session renewal (cookie expiry → re-login)
  Day 5: Integration test with staging portal
```

**Key Risks:**
- Portal UI changes frequently → maintain selector configs
- OTP timeout → must escalate to CA
- GSTN downtime on filing due date → queue for retry

**What NOT to do:**
- ❌ Don't hardcode selectors — use config file
- ❌ Don't skip idempotency check — never double-file
- ❌ Don't run parallel sessions for same firm + portal
- ❌ Don't ignore anti-bot detection — use stealth plugin

### Connector 7: WhatsApp Business (1 Week)

**API:** Meta Cloud API (REST) · Webhook for incoming messages

**Open Source Reference:**
- WhatsApp Business API: `WhatsApp Business Platform` (official)
- Python SDK: `pywhatkit` (community, limited)
- Webhook handling: Standard HTTP POST

**Build Steps:**
```
Day 1-2: Webhook setup (receive messages, verify webhook)
Day 3: Message processing (image → Gemini Vision extraction)
Day 4: Approval flow (send approval request → receive reply → process)
Day 5: Confirmation flow (send confirmation after action)
```

**What NOT to do:**
- ❌ Don't store WhatsApp credentials in code — use env vars
- ❌ Don't skip webhook verification — Meta requires it
- ❌ Don't send messages too fast — rate limit is 80 msgs/second

### Connector 8: Playwright Runtime (1 Week)

**Purpose:** Docker container for all portal automation

**Build Steps:**
```
Day 1: Dockerfile (mcr.microsoft.com/playwright/python:v1.44.0-jammy)
Day 2: FastAPI wrapper (start/stop/status endpoints)
Day 3: Session management (per-firm browser contexts)
Day 4: Health check (ping endpoint, screenshot on failure)
Day 5: Integration test
```

**Reference Dockerfile:**
```docker
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN playwright install chromium --with-deps
COPY . .
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
```

---

## Phase 2: Growth (Months 5-8) — 12 Connectors

| Priority | Connector | Build Time | Open Source Reference |
|----------|-----------|------------|----------------------|
| 9 | **Income Tax Portal** | 2 weeks | Playwright (same pattern as GSTN) |
| 10 | **Tally Prime** | 2 weeks | TallyXML bridge (HTTP to local port 18888) |
| 11 | **TRACES** | 2 weeks | Playwright + FVU format |
| 12 | **Account Aggregator** | 2 weeks | RBI AA framework API |
| 13 | **GSTN GSP API** | 2 weeks | GSP license (direct API, replaces Playwright) |
| 14 | **EPFO** | 1 week | ECR file format |
| 15 | **ESIC** | 1 week | Portal automation |
| 16 | **CAMS / KFintech** | 3 days | REST API |
| 17 | **Email (IMAP)** | 3 days | Python `imaplib` |
| 18 | **Sentry** | 1 day | `sentry-sdk` |
| 19 | **Langfuse** | 1 day | `langfuse` Python SDK |
| 20 | **QuickBooks** | 1 week | OAuth2 REST API |

### Tally Prime Bridge (Unique Challenge)

**Problem:** Tally has no REST API. Communication is via TallyXML over local HTTP port (18888).

**Open Source Reference:**
- TallyXML: `tallysolutions/tally-developer` (community)
- Bridge pattern: HTTP request → TallyXML → parse response

**Build Steps:**
```
Day 1-2: TallyXML client (HTTP to localhost:18888)
Day 3-4: Data extraction (Day Book, ledgers, TB via XML)
Day 5: Data writer (post journal entries via XML import)
Day 6: Sync manager (track what's synced, handle conflicts)
Day 7: Fallback (if Tally not running → suggest Excel upload)
```

**Key Risk:** Tally must be running on client's machine. If not, fall back to Excel upload.

---

## Phase 3: Scale (Months 9-18) — 12 Connectors

| Priority | Connector | Build Time |
|----------|-----------|------------|
| 21 | MCA21 | 2 weeks |
| 22 | SAP S/4HANA | 2 weeks |
| 23 | MS Dynamics 365 | 1 week |
| 24 | Oracle NetSuite | 1 week |
| 25 | HDFC Direct | 1 week |
| 26 | ICICI Direct | 1 week |
| 27 | Zerodha / Groww | 3 days |
| 28 | SMS Gateway | 2 days |
| 29 | Busy Accounting | 2 days |
| 30 | Marg ERP | 2 days |
| 31 | Excel / CSV | 2 days |
| 32 | Payroll Engine | 2 weeks |

---

## The MCP Server Pattern (For Every Connector)

### File Structure

```
connectors/
  zoho_books/
    __init__.py
    server.py              # MCP server entry point
    tools/
      fetch_purchase_register.py
      fetch_sales_register.py
      post_purchase_entry.py
    resources/
      organization_data.py
    auth/
      oauth_handler.py     # OAuth2 flow
      token_store.py       # Encrypted token storage
    client.py              # Typed API client
    schemas.py             # Pydantic models
    health.py              # Health check
```

### MCP Server Code Pattern

```python
from mcp.server import Server
from mcp.types import Tool, Resource
import json

server = Server("firmos-zoho-books")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="fetch_purchase_register",
            description="Fetch all purchase invoices for a period from Zoho Books",
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string", "description": "Client ID in firmOS"},
                    "period": {"type": "string", "description": "Tax period, e.g. '2026-05'"},
                },
                "required": ["client_id", "period"],
            },
        ),
        Tool(
            name="post_purchase_entry",
            description="Create a purchase entry in Zoho Books",
            inputSchema={
                "type": "object",
                "properties": {
                    "client_id": {"type": "string"},
                    "vendor_name": {"type": "string"},
                    "invoice_number": {"type": "string"},
                    "taxable_amount": {"type": "number"},
                    "cgst": {"type": "number"},
                    "sgst": {"type": "number"},
                },
                "required": ["client_id", "vendor_name", "invoice_number", "taxable_amount"],
            },
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "fetch_purchase_register":
        # 1. Get stored credentials
        creds = await get_zoho_credentials(arguments["client_id"])
        
        # 2. Call Zoho Books API
        purchases = await zoho_client.get_purchases(creds, arguments["period"])
        
        # 3. Return as MCP resource
        return [{"type": "text", "text": json.dumps(purchases, indent=2)}]
    
    if name == "post_purchase_entry":
        # CRITICAL: This writes to external system
        # Must go through approval workflow
        proposal = await create_proposal("zoho_books", "post_purchase", arguments)
        await interrupt(proposal)
        # Only executes after human approval
        result = await zoho_client.create_purchase(arguments)
        return [{"type": "text", "text": f"Posted. Ledger ref: {result['ledger_ref']}"}]
```

---

## The Approval Pattern (Non-Negotiable)

Every connector that writes to an external system:

```python
async def execute_with_approval(self, action: str, params: dict):
    # 1. Prepare
    draft = await self.prepare(action, params)
    
    # 2. Create proposal
    proposal = ActionProposal(
        connector=self.name,
        action=action,
        draft=draft,
        confidence=self.calculate_confidence(draft),
    )
    
    # 3. Wait for human approval (LangGraph interrupt)
    await interrupt(proposal)
    
    # 4. Execute after approval
    result = await self.commit(draft)
    
    # 5. Audit log
    await audit_log.record(proposal, result)
    
    return result
```

**What NEVER happens without approval:**
- Portal submission (GSTN, IT Portal, TRACES, MCA21)
- Ledger posting (Zoho Books)
- Bank transfer
- Any external correspondence

---

## What NOT to Do (Research-Backed)

### ❌ Don't Build These Yet

| Feature | Why Not Now |
|---------|-------------|
| **MCA21 connector** | Annual filings — low frequency, build in Phase 3 |
| **SAP connector** | Enterprise clients — niche, build in Phase 3 |
| **Mobile app** | Web app sufficient for MVP, build in Phase 3 |
| **Multi-firm support** | Single firm first, prove product-market fit |
| **Tally connector** | Complex (no API), build in Phase 2 after Zoho proves model |
| **Account Aggregator** | RBI approval takes 3-4 months, build in Phase 2 |
| **GSP license** | Apply now, but build Playwright first (faster to MVP) |

### ❌ Don't Make These Mistakes

| Mistake | Why It's Wrong |
|---------|---------------|
| **Build all 32 connectors at once** | You'll never finish. Build 8 for MVP, prove the model. |
| **Skip the approval workflow** | One wrong filing = lost CA client forever. `interrupt()` is non-negotiable. |
| **Hardcode portal selectors** | Government portals change UI frequently. Use config files. |
| **Skip idempotency** | Never double-file. Always check before submitting. |
| **Ignore anti-bot detection** | Playwright without stealth = blocked. Use `playwright-extra`. |
| **Store credentials in code** | Use encrypted vault (AES-256-GCM). Never in database plaintext. |
| **Build for enterprises first** | Start with solo CAs and MSMEs. Enterprises have 6-month sales cycles. |

### ❌ Don't Use These (For Each Connector)

| Connector | Don't Use | Use Instead |
|-----------|-----------|-------------|
| Zoho Books | Community Python SDK (unmaintained) | Direct REST API calls with `httpx` |
| GSTN Portal | Selenium (slow, detectable) | Playwright + stealth plugin |
| Tally | REST API (doesn't exist) | TallyXML over local HTTP port |
| WhatsApp | `pywhatkit` (limited) | Meta Cloud API (official) |
| Gemini Vision | Direct API calls | Vertex AI SDK (managed, DPDP compliant) |

---

## Cost Estimate

### Phase 1 (MVP)

| Item | Cost/month |
|------|-----------|
| Railway (API + Worker + Portal) | $50 |
| Supabase Pro | $25 |
| Upstash Redis | $0 (free tier) |
| Vertex AI (Gemini) | ~$5 |
| WhatsApp Business API | $0 (free 1K conversations) |
| Sentry | $0 (free 5K errors) |
| Langfuse | $0 (free 100K events) |
| **Total** | **~$80/month** |

### Phase 2 (Growth)

| Item | Cost/month |
|------|-----------|
| Railway (scaled) | $100 |
| Supabase Pro | $25 |
| Upstash Redis Pro | $20 |
| Vertex AI | ~$20 |
| Account Aggregator | ~$10 |
| CAMS API | ~$10 |
| **Total** | **~$185/month** |

---

## Timeline Summary

```
Month 1-4:   MVP (8 connectors)         → ₹50L ARR target
Month 5-8:   Growth (12 more connectors) → ₹3 Cr ARR target
Month 9-18:  Scale (12 more connectors)  → ₹15 Cr ARR target
```

---

## The One Thing That Matters

**Ship the MVP. Get 5 pilot CAs. Prove the model. Everything else follows.**

The connectors are the product. The approval workflow is the trust. The audit trail is the moat.

**Go build it.**
