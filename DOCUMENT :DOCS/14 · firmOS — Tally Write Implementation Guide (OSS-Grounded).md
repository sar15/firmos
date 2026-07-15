# firmOS — Tally Write Implementation Guide (OSS-Grounded)

**Status:** Canonical Implementation Guide & Gate Reference  
**Prerequisite Gates:**
1. **Gate 1 (Real CA Sign-Off):** Complete one real client loop (Real Bills $\rightarrow$ Purchase Register $\rightarrow$ Real Downloaded GSTR-2B $\rightarrow$ Recon $\rightarrow$ 3B Draft) with a human Chartered Accountant confirming 100% accurate numbers.
2. **Gate 2 (Licensed Tally Instance):** Confirmed licensed (non-Educational) Tally Prime instance. Educational versions silently corrupt date ranges and invalidate verification.

---

## 1. Core Architecture & Safety Rules

- **Bridge Pull Model:** Local daemon polls `GET /api/bridge/pending-commands` over outbound HTTPS. No inbound ports opened on the CA's machine.
- **Human HITL Approval Gate:** Every voucher write must pass through an explicit human CA approval gate before transmission.
- **Educational-Version Guard:** The daemon inspects Tally license status on startup and refuses write operations if running in Educational mode.
- **Write Seam Prohibition:** Until Gates 1 & 2 are cleared, write operations raise explicit `NotImplementedError` / `ProhibitedError`.

---

## 2. The Write Envelope (`<IMPORTDATA>` Contract)

Every write is an `Import Data` request POSTed to `http://localhost:9000` with `Content-Type: text/xml`:

```xml
<ENVELOPE>
  <HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="Purchase" ACTION="Create" OBJVIEW="Invoice Voucher View"
                   REMOTEID="firmos-{firm_id}-{doc_id}">
            <DATE>20260630</DATE>
            <PARTYLEDGERNAME>ACME Traders</PARTYLEDGERNAME>
            <VOUCHERTYPENAME>Purchase</VOUCHERTYPENAME>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>ACME Traders</LEDGERNAME>
              <ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE>   <!-- No = Credit -->
              <AMOUNT>590000.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
            <ALLLEDGERENTRIES.LIST>
              <LEDGERNAME>Purchase Account</LEDGERNAME>
              <ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE>  <!-- Yes = Debit -->
              <AMOUNT>-500000.00</AMOUNT>
            </ALLLEDGERENTRIES.LIST>
            <!-- + CGST/SGST/IGST ledger lines -->
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>
```

### Critical Rules:
1. **`ISDEEMEDPOSITIVE` Sign Contract:**
   - `Yes` = Debit $\rightarrow$ Amount in `<AMOUNT>` must be **negative** (e.g. `-500000.00`).
   - `No` = Credit $\rightarrow$ Amount in `<AMOUNT>` must be **positive** (e.g. `590000.00`).
   - All ledger lines in a voucher **must net exactly to zero**, otherwise Tally rejects with *"Voucher total does not match"*.
2. **Currency Boundary Conversion:**
   - Convert internal firmOS integer paise into rupees formatted to exactly 2 decimal places (`590000.00`).
   - Perform all rounding *before* balancing lines to avoid round-off rejections.

---

## 3. Idempotency: Use `REMOTEID` (Not Pre-Assigned GUID)

- **`REMOTEID` is Tally's Primary Key for Imports:**
  - Format: `firmos-{firm_id}-{doc_id}` (deterministic across retries).
  - If a voucher with that `REMOTEID` exists, Tally executes an **Update** (`<ALTERED>1</ALTERED>`).
  - If absent, Tally executes a **Create** (`<CREATED>1</CREATED>`).
- **GUIDs are Assigned Post-Import:**
  - Never set `GUID` or `MasterID` on create requests. Tally assigns internal GUIDs upon import.
  - After a successful write, record the mapping `REMOTEID -> Tally GUID` returned or queried for auditability.

---

## 4. Pre-Flight Master Creation (Ledgers First)

Tally rejects vouchers if referenced ledgers do not exist. Before posting any voucher:
1. Ensure required ledgers exist or push `Import Data` with `ACTION="Create"` for missing ledgers:
   - Party Ledger under *Sundry Creditors / Sundry Debtors*.
   - Purchase / Sales Account Ledgers.
   - Tax Ledgers (*Duties & Taxes* for CGST / SGST / IGST).
2. Escape XML entities (`&` $\rightarrow$ `&amp;`, `<` $\rightarrow$ `&lt;`).

---

## 5. Response Verification

Never trust an HTTP `200 OK` alone. Parse the XML response body:
- Assert `<ERRORS>0</ERRORS>`.
- Assert `<CREATED>1</CREATED>` (or `<ALTERED>1</ALTERED>` on update).
- If `<ERRORS> > 0`, extract `<LINEERROR>` text and inspect `tally.imp` logs.
