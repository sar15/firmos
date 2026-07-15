# firmOS — Canonical Build Sequence: Option B (Corrected & De-Mocked)
**Status:** Canonical Execution Roadmap  
**Governing Strategy:** Manual-Portal v1 (No GSP Production Key Dependency)  
**Primary Production Gate:** *ONE Real Client End-to-End Human CA Verified Numbers (Zero Mocks).*

---

## 1. Core Strategic Confirmation: Manual Portal Strategy

### Answer: **YES — 100% MANUAL PORTAL STRATEGY FOR v1.**
- **Why:** Waiting for third-party WhiteBooks/GSTN GSP production API credentials blocks your critical path to first practice revenue.
- **How It Works:**
  - **GSTR-2B Ingestion:** CA uploads downloaded portal JSON file (`POST /api/reconciliation/upload-2b` scoped by firm + client RLS).
  - **GSTR-3B Submission:** Emits complete copy-paste table layout (`3.1a–e`, `3.2`, `4A–D`, `5`, `6.1`) AND official GSTN GSTR-3B JSON for direct portal upload.

---

## 2. Canonical Build Sequence: Phases 0 to 4

```
Phase 0  De-mock Spine & Guard (PREREQUISITE — STRICT_NO_MOCK guard + 5 named de-mocks)
Phase 1  GSTR-2B JSON Parser   (Linchpin: parse portal JSON ctin/inv/cdnr/cdnra -> ReconLine)
Phase 2  3B Table & JSON Emit  (Exact portal table layout + GSTN offline JSON format)
Phase 3  ONE-Client Proof ✅    ← THE REAL v1 GATE (Human CA sign-off on real client numbers)
Phase 4  Tally Read -> Write   (Attach local XML bridge only after spine is verified)
```

---

### Phase 0: De-Mock the Spine & Schema Alignment (Prerequisite · 1–2 Days)
1. **Runtime Guard:** Introduce `STRICT_NO_MOCK=true` flag in `core/config.py`. When active, any fallback path raises `RuntimeError("STRICT_NO_MOCK enforced")`.
2. **Schema Alignment (`models/schemas.py` L107):** Align `docKind` exactly with frontend Zod schema:
   ```python
   docKind: Literal["VENDOR_BILL", "SALES_INVOICE", "RECEIPT", "PAYMENT", "JOURNAL"]
   ```
3. **Prompt Architecture (`extraction/sarvam.py`):** Move document classification prompt from `gemini.py` into `sarvam.py`.
4. **Five Explicit De-Mocks:**
   - `api/routes/zoho.py` (`compute_gst_summary`): delete mock fallback return.
   - `api/routes/reconciliation.py`: delete `_mock_source` / `_mock_target`.
   - `workflows/graphs.py` (`t4_compute`): delete hardcoded `500000 / 200000 / 150000`.
   - `connectors/gst_filing/whitebooks/client.py`: ensure `dummy_token` and `ARN-FILED-12345` are stripped from operational paths.

---

### Phase 1: GSTR-2B Portal JSON File Parser (~2–3 Days)
- **Input:** Standard GSTR-2B JSON file downloaded by the CA from the GST portal.
- **Sections Handled:** `b2b` regular invoices, `cdnr` credit/debit notes, `b2ba` amendments, `cdnra` note amendments, plus logging `impg` / `impgsez` import ITC.
- **Output:** Transforms into canonical `list[ReconLine]` items matching `engines/reconcile.py` contract.
- **Endpoint:** `POST /api/reconciliation/upload-2b` scoped by firm + client RLS.

---

### Phase 2: Complete GSTR-3B Table Layout & JSON Generator (~2 Days)
- **Tables Handled:**
  - Table 3.1: Outward taxable (a), Zero-rated (b), Nil/exempt (c), Inward RCM (d), Non-GST (e)
  - Table 3.2: Inter-state supplies to unregistered/composition/UIN
  - Table 4 (ITC): 4(A) Available, 4(B) Reversed, 4(C) Net Available, 4(D) Ineligible
  - Table 5: Exempt/nil inward
  - Table 6.1: Payment of tax breakdown
- **Fast-Follow:** Emit official GSTN GSTR-3B offline JSON format for direct portal upload.

---

### Phase 3: ONE-Client End-to-End Proof (THE REAL v1 GATE)
- Run ONE real client data set through `Real Bills -> Purchase Register -> Real 2B JSON -> Reconciliation -> GSTR-3B Table & JSON` under `STRICT_NO_MOCK=true`.
- Chartered Accountant signs off that every table cell matches the books 100%.

---

### Phase 4: Attach Tally Prime (Read $\rightarrow$ Write)
- Attach `bridge_daemon.py` `<IMPORTDATA>` XML engine behind the `interrupt(review_gate)` CA human approval gate with GUID deduplication and UDF/REMOTEID idempotency.
