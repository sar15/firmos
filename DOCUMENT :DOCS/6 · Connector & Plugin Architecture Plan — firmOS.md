# 6 · Connector & Plugin Architecture Plan — firmOS

## firmOS · Complete Connector/Plugin System — June 2026

**Version 1.0 · June 2026 · Production-grade architecture**

---

## Philosophy

> firmOS is only as good as its connectors. The agent does the thinking. The connectors do the talking. Every connector follows one rule: **read freely, write with approval, never double-commit.**

---

## The Three Connector Tiers

| Tier | Description | Example | Auth | Risk |
|------|-------------|---------|------|------|
| **Tier 1: Live API** | Direct REST/OAuth API. Clean, typed, reliable. | Zoho Books, WhatsApp, Gemini Vision | OAuth2 / API Key | Low |
| **Tier 2: Portal Automation** | Playwright browser automation. Brittle but necessary. | GSTN, IT Portal, TRACES, MCA21 | Credentials + OTP | High |
| **Tier 3: File-Based** | Upload XLSX/CSV/PDF. Manual but universal. | Busy, Marg, Excel, bank statements | None (user uploads) | None |

---

## Complete Connector Inventory

### CATEGORY 1: ACCOUNTING SOFTWARE

| # | Connector | Tier | Auth | Read | Write | Difficulty | Build Time | Notes |
|---|-----------|------|------|------|-------|------------|------------|-------|
| 1 | **Zoho Books** | 1 | OAuth2 | ✅ | ✅ | 🟢 Easy | 1 week | Official API, clean docs, webhook support |
| 2 | **Tally Prime** | 2 | Desktop Bridge | ✅ | ✅ | 🟡 Medium | 2 weeks | No REST API — TallyXML import/export via本地 server |
| 3 | **QuickBooks** | 1 | OAuth2 | ✅ | ❌ | 🟢 Easy | 3 days | Read-only for MVP, write in Phase 2 |
| 4 | **Busy Accounting** | 3 | Upload | ✅ | ❌ | 🟢 Easy | 2 days | XLSX export from Busy reports menu |
| 5 | **Marg ERP** | 3 | Upload | ✅ | ❌ | 🟢 Easy | 2 days | Day Book + TB Excel export |
| 6 | **MS Dynamics 365** | 1 | OAuth2 | ✅ | ❌ | 🟡 Medium | 1 week | BC / F&O — Send-to-Excel + OData API |
| 7 | **Oracle NetSuite** | 1 | OAuth2 | ✅ | ❌ | 🟡 Medium | 1 week | SuiteQL + saved-search exports |
| 8 | **SAP S/4HANA** | 1 | Enterprise API | ✅ | ❌ | 🔴 Hard | 2 weeks | OData (S/4HANA + B1) or upload fallback |
| 9 | **Excel / CSV** | 3 | Upload | ✅ | ❌ | 🟢 Easy | 2 days | Universal fallback — any system that exports GL + TB |

**Total accounting connectors: 9**

---

### CATEGORY 2: GOVERNMENT PORTALS

| # | Connector | Tier | Auth | Read | Write | Difficulty | Build Time | Notes |
|---|-----------|------|------|------|-------|------------|------------|-------|
| 10 | **GSTN Portal** | 2 | Credentials + OTP | ✅ | ✅ | 🔴 Hard | 3 weeks | Playwright MVP → GSP License Phase 2 |
| 11 | **Income Tax Portal** | 2 | Credentials + OTP | ✅ | ✅ | 🔴 Hard | 2 weeks | 26AS, AIS, ITR filing |
| 12 | **TRACES** | 2 | Credentials | ✅ | ✅ | 🔴 Hard | 2 weeks | TDS returns, FVU file generation |
| 13 | **MCA21** | 2 | Credentials + DSC | ✅ | ✅ | 🔴 Hard | 2 weeks | MGT-7, AOC-4 filing |
| 14 | **EPFO** | 2 | Credentials | ✅ | ✅ | 🟡 Medium | 1 week | ECR file generation, PF returns |
| 15 | **ESIC** | 2 | Credentials | ✅ | ✅ | 🟡 Medium | 1 week | ESI return filing |
| 16 | **GSTN GSP API** | 1 | GSP License | ✅ | ✅ | 🟡 Medium | 2 weeks | Phase 2 — replaces Playwright for GST |

**Total government connectors: 7**

---

### CATEGORY 3: BANKING & FINANCIAL DATA

| # | Connector | Tier | Auth | Read | Write | Difficulty | Build Time | Notes |
|---|-----------|------|------|------|-------|------------|------------|-------|
| 17 | **Account Aggregator (AA)** | 1 | Consent (RBI) | ✅ | ❌ | 🟡 Medium | 2 weeks | HDFC, ICICI, SBI — programmatic bank data |
| 18 | **HDFC Direct** | 2 | Playwright | ✅ | ❌ | 🟡 Medium | 1 week | Bank statement download (AA fallback) |
| 19 | **ICICI Direct** | 2 | Playwright | ✅ | ❌ | 🟡 Medium | 1 week | Bank statement download (AA fallback) |
| 20 | **CAMS / KFintech** | 1 | API | ✅ | ❌ | 🟢 Easy | 3 days | Mutual fund capital gains statements |
| 21 | **Zerodha / Groww** | 1 | API | ✅ | ❌ | 🟢 Easy | 3 days | Broker capital gains statements |

**Total banking connectors: 5**

---

### CATEGORY 4: DOCUMENT & COMMUNICATION

| # | Connector | Tier | Auth | Read | Write | Difficulty | Build Time | Notes |
|---|-----------|------|------|------|-------|------------|------------|-------|
| 22 | **WhatsApp Business** | 1 | Meta Cloud API | ✅ | ✅ | 🟢 Easy | 1 week | Webhook + send — bill receipt + approvals |
| 23 | **Gemini Vision** | 1 | API Key | ✅ | ❌ | 🟢 Easy | 3 days | PDF/image extraction — Form 16, bank stmts |
| 24 | **Email (IMAP)** | 1 | Credentials | ✅ | ❌ | 🟢 Easy | 3 days | Receive documents from clients via email |
| 25 | **SMS Gateway** | 1 | API Key | ❌ | ✅ | 🟢 Easy | 2 days | OTP delivery, client notifications |

**Total document connectors: 4**

---

### CATEGORY 5: INFRASTRUCTURE (Developer)

| # | Connector | Tier | Auth | Read | Write | Difficulty | Build Time | Notes |
|---|-----------|------|------|------|-------|------------|------------|-------|
| 26 | **Supabase** | 1 | SDK | ✅ | ✅ | 🟢 Easy | Already done | Database, auth, storage |
| 27 | **Vertex AI (Gemini)** | 1 | Service Account | ✅ | ❌ | 🟢 Easy | Already done | AI model for extraction |
| 28 | **LangGraph** | 1 | Local | ✅ | ✅ | 🟢 Easy | Already done | Agent workflow orchestration |
| 29 | **Playwright Runtime** | 2 | Docker | ✅ | ✅ | 🟡 Medium | 1 week | Portal automation container |
| 30 | **Redis (Upstash)** | 1 | URL | ✅ | ✅ | 🟢 Easy | Already done | Job queue, session cache |
| 31 | **Sentry** | 1 | DSN | ✅ | ❌ | 🟢 Easy | 1 day | Error tracking |
| 32 | **Langfuse** | 1 | API Key | ✅ | ❌ | 🟢 Easy | 1 day | LLM call logging |

**Total infrastructure connectors: 7**

---

## Summary

| Category | Count | Easy | Medium | Hard |
|----------|-------|------|--------|------|
| Accounting Software | 9 | 5 | 2 | 2 |
| Government Portals | 7 | 0 | 2 | 5 |
| Banking & Financial | 5 | 3 | 2 | 0 |
| Document & Communication | 4 | 4 | 0 | 0 |
| Infrastructure | 7 | 5 | 2 | 0 |
| **TOTAL** | **32** | **17** | **8** | **7** |

---

## Build Order (Recommended)

### Phase 1: MVP (Months 1-4) — 8 Connectors

| Priority | Connector | Why First |
|----------|-----------|-----------|
| 1 | Supabase | Already done — foundation |
| 2 | Vertex AI (Gemini) | Already done — document extraction |
| 3 | LangGraph | Already done — workflow engine |
| 4 | Redis | Already done — job queue |
| 5 | **Zoho Books** | First accounting connector — OAuth2, clean API |
| 6 | **GSTN Portal** (Playwright) | Most-used government portal — critical for GSTR-3B |
| 7 | **WhatsApp Business** | Client communication — bill receipt channel |
| 8 | **Playwright Runtime** | Portal automation Docker container |

### Phase 2: Growth (Months 5-8) — 12 Connectors

| Priority | Connector | Why Now |
|----------|-----------|---------|
| 9 | **Income Tax Portal** | ITR filing — second most-used portal |
| 10 | **Tally Prime** | Desktop bridge — covers 60%+ of Indian CA market |
| 11 | **TRACES** | TDS returns — quarterly workflow |
| 12 | **Account Aggregator** | Bank data — eliminates manual upload |
| 13 | **GSTN GSP API** | Replace Playwright for GST — more reliable |
| 14 | **EPFO** | Payroll compliance |
| 15 | **ESIC** | Payroll compliance |
| 16 | **CAMS / KFintech** | Capital gains for ITR |
| 17 | **Email (IMAP)** | Document intake channel |
| 18 | **Sentry** | Error tracking |
| 19 | **Langfuse** | LLM monitoring |
| 20 | **QuickBooks** | International clients |

### Phase 3: Scale (Months 9-18) — 12 Connectors

| Priority | Connector | Why Later |
|----------|-----------|-----------|
| 21 | MCA21 | Annual filings — low frequency |
| 22 | SAP S/4HANA | Enterprise clients — niche |
| 23 | MS Dynamics 365 | Enterprise clients — niche |
| 24 | Oracle NetSuite | Enterprise clients — niche |
| 25 | HDFC Direct | AA fallback — when AA isn't available |
| 26 | ICICI Direct | AA fallback |
| 27 | Zerodha / Groww | Broker APIs — Phase 3 capital gains |
| 28 | SMS Gateway | Notifications — WhatsApp covers most cases |
| 29 | Busy Accounting | Upload-based — low priority |
| 30 | Marg ERP | Upload-based — low priority |
| 31 | Excel / CSV | Universal fallback — always available |
| 32 | Payroll Engine | State-specific PT variations — complex |

---

## Connector Architecture (Python)

### Base Interface

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from enum import Enum

class ConnectorTier(str, Enum):
    LIVE_API = "LIVE_API"
    PORTAL_AUTOMATION = "PORTAL_AUTOMATION"
    FILE_BASED = "FILE_BASED"

class ConnectorCapability(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    SUBMIT = "SUBMIT"  # Portal filing
    FILE = "FILE"       # Return filing

class ConnectorStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    NEEDS_ATTENTION = "NEEDS_ATTENTION"
    COMING_SOON = "COMING_SOON"

class ConnectorConfig(BaseModel):
    firm_id: str
    client_id: str
    auth_method: str
    credentials_encrypted: str
    rate_limit: int = 100

class ConnectorHealth(BaseModel):
    status: ConnectorStatus
    last_checked: str
    latency_ms: int | None
    error_message: str | None

class BaseConnector(ABC):
    """Every connector must implement this interface"""
    
    id: str
    name: str
    category: str
    tier: ConnectorTier
    capabilities: list[ConnectorCapability]
    auth_method: str
    description: str
    badge_color: str
    badge_label: str
    
    @abstractmethod
    async def health_check(self) -> ConnectorHealth:
        """Ping the service, verify credentials"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> dict:
        """Test connection and return sample data"""
        pass
    
    @abstractmethod
    def get_status(self) -> ConnectorStatus:
        """Return current connection status"""
        pass
```

### Connector Registry

```python
class ConnectorRegistry:
    """Central registry for all firmOS connectors"""
    
    _connectors: dict[str, BaseConnector] = {}
    
    def register(self, connector: BaseConnector) -> None:
        self._connectors[connector.id] = connector
    
    def get(self, connector_id: str) -> BaseConnector | None:
        return self._connectors.get(connector_id)
    
    def list_by_category(self, category: str) -> list[BaseConnector]:
        return [c for c in self._connectors.values() if c.category == category]
    
    def list_by_tier(self, tier: ConnectorTier) -> list[BaseConnector]:
        return [c for c in self._connectors.values() if c.tier == tier]
    
    def list_for_workflow(self, workflow_type: str) -> list[BaseConnector]:
        """Return connectors needed for a specific workflow"""
        WORKFLOW_CONNECTORS = {
            "GSTR_3B": ["gstn_portal", "zoho_books", "gemini_vision"],
            "ITR_4": ["it_portal", "zoho_books", "gemini_vision", "cams"],
            "TDS_26Q": ["traces", "zoho_books"],
            "PAYROLL": ["epfo", "esic", "zoho_books"],
            "BANK_RECON": ["zoho_books", "bank_statement"],
            "VENDOR_BILL": ["whatsapp", "gemini_vision", "zoho_books"],
        }
        connector_ids = WORKFLOW_CONNECTORS.get(workflow_type, [])
        return [self._connectors[cid] for cid in connector_ids if cid in self._connectors]
    
    def get_recommendation(self, client_size: str, state: str) -> str:
        """Smart ERP recommendation"""
        if client_size == "SME":
            return "tally_prime"
        if client_size == "ENTERPRISE":
            return "sap_s4hana"
        return "zoho_books"
```

### Connector Card (Frontend)

```typescript
// The Coraa-inspired connector card for firmOS
interface ConnectorCardData {
  id: string;
  name: string;
  category: "ACCOUNTING" | "GOVERNMENT" | "BANKING" | "DOCS" | "DEVELOPER";
  integrationType: "LIVE_CONNECTOR" | "OAUTH_API" | "ENTERPRISE_API" | "PLAYWRIGHT" | "UPLOAD" | "COMING_SOON";
  capabilities: ("READ" | "WRITE" | "SUBMIT" | "FILE")[];
  status: "CONNECTED" | "DISCONNECTED" | "NEEDS_ATTENTION" | "COMING_SOON";
  description: string;
  recommended?: boolean;
  lastSyncedAt?: string;
  healthStatus?: "healthy" | "degraded" | "down";
}
```

---

## Auth Patterns by Connector Type

| Pattern | Connectors | Implementation |
|---------|-----------|----------------|
| **OAuth2** | Zoho Books, QuickBooks, WhatsApp, MS Dynamics, NetSuite | Store refresh token encrypted. Auto-refresh before expiry. |
| **Credentials + OTP** | GSTN, IT Portal, TRACES, MCA21 | Store username/password encrypted. Playwright session management. OTP via WhatsApp/SMS. |
| **Desktop Bridge** | Tally Prime | Tally runs locally. Bridge script connects via TallyXML. |
| **Consent (AA)** | Account Aggregator | RBI AA framework — user consents via AA app. |
| **API Key** | Gemini Vision, CAMS, Zerodha | Store API key encrypted. |
| **DSC (Manual)** | GSTN, IT Portal, MCA21 | Cannot automate — CA must sign. Agent prepares, human signs. |
| **File Upload** | Busy, Marg, Excel, bank statements | User uploads XLSX/CSV/PDF. Gemini Vision extracts data. |

---

## The Connector Onboarding Wizard (5 Steps)

Like Coraa's pattern, every new engagement follows:

```
Step 1: CLIENT          → Select or create client profile
Step 2: ERP             → Which accounting software? (card grid with badges)
Step 3: PORTALS         → Which government portals to connect?
Step 4: WORKFLOWS       → Which compliance workflows to enable?
Step 5: CONFIRM         → Review setup, test connections, activate
```

### Step 2: ERP Selection (Coraa-Inspired)

```
┌─────────────────────────────────────────────────────────┐
│  NEW ENGAGEMENT                                         │
│  Step 2 of 5 · ERP                                      │
│                                                         │
│  Which ERP does the client use?                         │
│  Tally has a live connector (recommended for SME).      │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ ● Tally  │ │ ○ Zoho   │ │ ○ SAP    │               │
│  │ 🟢 Live  │ │ 🔵 OAuth │ │ 🟠 Ent.  │               │
│  │ Default. │ │ OAuth2.  │ │ OData +  │               │
│  │ Desktop  │ │ Read     │ │ upload   │               │
│  └──────────┘ └──────────┘ └──────────┘               │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐               │
│  │ ○ Busy   │ │ ○ Dyna.. │ │ ○ NetS.. │               │
│  │ ⚪ Upload│ │ ⚪ Soon   │ │ ⚪ Upload│               │
│  └──────────┘ └──────────┘ └──────────┘               │
│                                                         │
│  Pick any active ERP to continue.          [Next →]    │
└─────────────────────────────────────────────────────────┘
```

### Badge System (Coraa-Inspired + Extended)

| Badge | Color | Meaning | firmOS Use |
|-------|-------|---------|------------|
| **Live Connector** | 🟢 Green | Direct API, real-time, read+write | Tally (desktop), Zoho Books |
| **OAuth API** | 🔵 Blue | Secure OAuth2 flow | Zoho Books, QuickBooks, WhatsApp |
| **Enterprise API** | 🟠 Orange | High-volume, complex auth | SAP S/4HANA, Oracle NetSuite |
| **Playwright** | 🟣 Purple | Browser automation | GSTN, IT Portal, TRACES, MCA21 |
| **Upload** | ⚪ Grey | Manual file upload | Busy, Marg, Excel/CSV |
| **Consent (AA)** | 🔵 Teal | RBI Account Aggregator | HDFC, ICICI bank data |
| **Manual** | ⚪ Light Grey | Human must do it | DSC signing, physical documents |
| **Coming Soon** | ⚪ Light Grey | Planned, not enabled | MS Dynamics, QuickBooks (Phase 2) |

---

## Difficulty Deep-Dive: The Hard Connectors

### 🔴 GSTN Portal (Playwright) — 3 Weeks

**Why hard:**
- No public API — only portal or GSP
- Portal UI changes frequently (selectors break)
- OTP during filing — must pause and notify CA
- Session management — cookies expire, re-login needed
- Anti-bot detection — must look human
- Idempotency — must never double-file

**Architecture:**
```
GSTN Portal Automation
├── session_manager.py     # Login, cookie persistence, re-login
├── gstr2b_downloader.py   # Download GSTR-2B for period
├── gstr3b_filler.py       # Fill GSTR-3B tables
├── otp_handler.py         # Pause → notify CA → enter OTP
├── submission.py          # Submit + capture ARN
├── anti_detection.py      # Human-like delays, stealth plugin
└── failure_capture.py     # Screenshot on error
```

**Key risks:**
- Portal UI change → selectors break → workflow fails
- GSTN downtime on filing due date → must retry
- OTP timeout → must escalate to CA

### 🔴 Income Tax Portal (Playwright) — 2 Weeks

**Why hard:**
- Complex multi-step filing flow
- 26AS and AIS download requires specific navigation
- ITR JSON upload + submission
- E-verification flow (Aadhaar OTP or net banking)
- Portal frequently goes down during filing season

### 🔴 TRACES (Playwright) — 2 Weeks

**Why hard:**
- FVU file format is complex (NSDL specification)
- Challan matching logic is non-trivial
- PAN validation requires IT Portal API
- Multiple return types (24Q, 26Q, 27Q, 27EQ)

### 🟡 Tally Prime (Desktop Bridge) — 2 Weeks

**Why hard:**
- No REST API — Tally communicates via XML over local port
- Tally must be running on the client's machine
- Data extraction via TallyXML request/response
- Writing back to Tally requires XML import

**Architecture:**
```
Tally Bridge
├── tally_xml_client.py    # HTTP client to Tally's local port (18888)
├── data_extractor.py      # Request Day Book, ledgers, TB via XML
├── data_writer.py         # Post journal entries via XML import
├── sync_manager.py        # Track what's synced, handle conflicts
└── fallback.py            # If Tally not running → suggest Excel upload
```

---

## The `interrupt()` Pattern (Non-Negotiable)

Every connector that writes to an external system:

```python
async def execute_with_approval(self, action: str, params: dict) -> ActionProposal:
    # 1. Prepare the action
    draft = await self.prepare(action, params)
    
    # 2. Create proposal (LangGraph interrupt)
    proposal = ActionProposal(
        connector=self.name,
        action=action,
        draft=draft,
        confidence=self.calculate_confidence(draft),
        flags=self.check_flags(draft),
    )
    
    # 3. Wait for human approval
    await interrupt(proposal)
    
    # 4. Only execute after approval
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

## File Structure

```
connectors/
  __init__.py              # Registry auto-registration
  base.py                  # BaseConnector + ConnectorPlugin protocol
  registry.py              # ConnectorRegistry
  onboarding_wizard.py     # 5-step engagement wizard
  
  accounting/
    __init__.py
    zoho_books/
      connector.py
      auth.py              # OAuth2 handler
      schemas.py           # Pydantic models
      client.py            # Typed API client
    tally/
      connector.py
      tally_xml_client.py  # TallyXML bridge
      data_extractor.py
    quickbooks/
      connector.py
      auth.py
    busy/
      connector.py         # Upload handler
    marg/
      connector.py         # Upload handler
    sap/
      connector.py         # OData client
    dynamics/
      connector.py         # OData client
    netsuite/
      connector.py         # SuiteQL client
    excel/
      connector.py         # Universal CSV/XLSX parser
  
  government/
    __init__.py
    gstn/
      connector.py
      session_manager.py
      gstr2b_downloader.py
      gstr3b_filler.py
      otp_handler.py
      anti_detection.py
    it_portal/
      connector.py
      session_manager.py
      form26as_fetcher.py
      ais_fetcher.py
      itr_filer.py
    traces/
      connector.py
      fvu_generator.py
      challan_matcher.py
    mca21/
      connector.py
      xml_generator.py
    epfo/
      connector.py
      ecr_generator.py
    esic/
      connector.py
  
  banking/
    __init__.py
    account_aggregator/
      connector.py
      consent_manager.py
    hdfc/
      connector.py
    icici/
      connector.py
    cams/
      connector.py
    zerodha/
      connector.py
  
  docs/
    __init__.py
    whatsapp/
      connector.py
      webhook_handler.py
      message_templates.py
    gemini_vision/
      connector.py
      document_extractor.py
      prompts/
        vendor_bill.txt
        bank_statement.txt
        form_16.txt
        notice.txt
    email/
      connector.py
    sms/
      connector.py
```

---

## Cost Estimate (Per Connector)

| Connector | API Cost | Hosting | Total/month |
|-----------|----------|---------|-------------|
| Zoho Books | Free (within Zoho sub) | — | $0 |
| GSTN Playwright | — | $20 (Railway Docker) | $20 |
| IT Portal Playwright | — | Shared with GSTN | $0 |
| WhatsApp Business | Free first 1K conversations | — | $0 |
| Gemini Vision | ~₹1.5 per 100 docs | — | ~$5 |
| Account Aggregator | ₹2-5 per consent | — | ~$10 |
| CAMS API | ₹5 per transaction | — | ~$10 |
| Sentry | Free (5K errors/month) | — | $0 |
| Langfuse | Free (100K events/month) | — | $0 |
| **Total (MVP)** | | | **~$45/month** |

---

## Summary

| Metric | Value |
|--------|-------|
| Total connectors planned | 32 |
| MVP connectors (Phase 1) | 8 |
| Easy to build | 17 (53%) |
| Medium difficulty | 8 (25%) |
| Hard | 7 (22%) |
| Total build time (all phases) | ~16 weeks |
| Monthly hosting cost (MVP) | ~$45 |
| Monthly hosting cost (Scale) | ~$200 |

**The 7 hard connectors are all government portals.** Everything else is straightforward. The government portal automation is firmOS's engineering moat — competitors must rebuild it from scratch.
