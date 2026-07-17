# firmOS Comprehensive Codebase Audit Report

**Date**: 2026-07-17  
**Scope**: `apps/web`, `firmos-backend`, `firmos-bridge`  

---

## 1. Executive Summary

This final, master audit report synthesizes the detailed findings of all 8+ background agent teams across multiple independent audit systems (including the original Milestone Explorers, Orchestrators, and the Teamwork Multi-Agent teams) that evaluated the firmOS codebase. 

The application suffers from critical compliance and calculation bugs in the backend engines, widespread architectural layer violations in the frontend, a critical crash on the Connectors page, and frequent deviations from strict UX/UI styling rules.

---

## 2. Connectors Page Failure Investigation (Milestone 1)

* **Symptom**: The `/connectors` page shows `"Connectors could not be loaded. Please retry."` and the network shows a `500 Internal Server Error` on `GET /api/clients`.
* **Frontend Path**: `ConnectorsClient.tsx` triggers `Promise.all([..., listClients()])` which fails.
* **Backend Path**: `/api/clients` tries to parse a database row where `books_provider` is `None` (NULL). The code maps `None` to `""`.
* **Pydantic Validation Error**: The `Client` model strictly requires `"ZOHO_BOOKS", "TALLY", "QUICKBOOKS", "CSV", or "NONE"`. The empty string `""` triggers a `ValidationError`. 
* **Remediation Needed**: Restart the FastAPI server to load the updated schema that accepts `"NONE"` and fix the route mapping.

---

## 3. Business Logic, Calculations & Statutory Engines (Critical)

### 3.1 GST Compliance & Calculations
- **GST Component-Wise Offset Mismatch**: `firmos-backend/engines/gst.py`. The logic evaluates GST liability as a single scalar pool instead of component-wise (IGST, CGST, SGST) prioritization under Section 49 / Rule 88A.
- **GSTR-3B Cross-Component Offsets Broken**: `firmos-backend/engines/gst.py`. Code restricts offsets strictly within the same component, failing to allow statutory cross-utilization of ITC across components.

### 3.2 Income Tax & TDS Calculations
- **Section 234C Interest Deferment Buffer Missing**: `firmos-backend/engines/interest.py`. Enforces nominal 15% and 45% values, ignoring statutory interest waiver thresholds.
- **Section 234B/234C Rule 119A Rounding Violation**: `firmos-backend/engines/interest.py`. Interest is computed directly on raw shortfall instead of rounding the shortfall down to multiples of ₹100.
- **Wrong Assessment Year Start**: `firmos-backend/engines/interest.py`. `ay_start = date(assessment_year_end.year, 4, 1)` calculates the period 12 months late. It should be `year - 1`.
- **Incorrect New Tax Regime Slabs (FY 24-25)**: `firmos-backend/engines/tax.py`. Uses outdated 7L/10L boundaries instead of the correct 6L/9L slabs from Finance Act 2024.
- **TDS Section 206AA No-PAN Penalty**: `firmos-backend/engines/tds.py`. Applies `min(rate * 2, 20.0)` which caps the rate at a maximum instead of applying the statutory minimum floor of 20%.
- **TDS Section 194Q Threshold & Errors**: `firmos-backend/engines/tds.py`. Threshold is 10x too high (₹5 Crore instead of ₹50 Lakhs), and calculated on the gross amount rather than the excess.
- **Chapter VI-A Deductions in New Regime**: `firmos-backend/engines/income_tax_rules.py`. Unconditionally subtracts Chapter VI-A deductions, which should be disallowed in the New Regime.

### 3.3 Core Logic & Validation
- **Flipped Books vs. GSTR-2B Panes**: `firmos-backend/engines/reconcile.py`. Puts unmatched target (GSTR-2B) rows into the `source` (Books) property, flipping the visualization on the frontend and incorrectly flagging as `"SUPPLIER_NOT_FILED"`.
- **Invalid State Code Comparison**: `firmos-backend/core/purchase_invoices/validation.py`. Compares 2-digit state code of a GSTIN (e.g. "27") directly with textual state name (e.g. "Maharashtra"), which always fails.

---

## 4. Backend Architecture, Integrations & Data Integrity

- **Bridge Sync Idempotency Defeat**: `firmos-bridge/bridge_daemon.py`. Generates a fresh UUID idempotency key on each loop execution, meaning a network retry submits a new key and risks duplicate data.
- **Transaction Table Locks**: `firmos-backend/connectors/tally/ingest.py`. Inserts thousands of records sequentially (`await conn.execute`) inside a single long-lived transaction loop, causing database locks.
- **Runtime Crash Risk (asyncpg.Record)**: `firmos-backend/api/routes/decision_format.py`. Formatter attempts to call `.get()` on an `asyncpg.Record`, resulting in an `AttributeError`.
- **Bypassed OAuth Refresh Cache**: `firmos-backend/api/routes/zoho.py`. Instantiates `ZohoClient` without passing a database refresh callback, resulting in an external Zoho OAuth hit on *every* request after expiration.
- **Hardcoded First Active Firm Membership**: `firmos-backend/api/deps.py`. Queries the first active membership ordered by creation date, preventing users from switching firms.
- **Unbounded Growth of Device Nonces**: `firmos-backend/api/routes/tally_agent_auth.py`. Inserts nonces on every request with no cleanup trigger, leading to unbounded DB growth.
- **Restricted Date Format Parsing**: `firmos-backend/api/routes/bank_statement_parsing.py`. Fails to parse abbreviated months (e.g., "12-Jan-2026") or 2-digit years.
- **File Length Cap Violation**: `connector_zoho_oauth.py` has 307 lines of code, violating the strict 300 LOC limit.

---

## 5. Frontend Architecture & Code Structure

### 5.1 Feature Layers (Separation of Concerns)
- **Verbatim State in Components**: Almost 100% of `.tsx` files in `features/` maintain local state and fetch APIs directly, violating the rule that `*.tsx` should be "dumb UI" and logic should reside in `use*.ts` hooks.
- **Client/Server Split**: Page components under `apps/web/src/app/` are marked `"use client"` and manage active fetching instead of being thin Server Components.

### 5.2 Directory Organization & Conventions
- **Misplaced Features**: `NotificationsPanel.tsx` sits in generic components instead of `features/notifications/`.
- **Flat Backend**: The backend is organized by technical layers instead of feature slices.
- **Duplicate Types**: `AuditEntry` is defined globally but overwritten with a conflicting schema in `agent.api.ts`.
- **Casing & Abbreviations**: Arrow functions are not used for components (`export function`). Unapproved abbreviations (`Recon`, `Auth`, `Kbd`) are scattered throughout. Python standard `snake_case` is leaking into TypeScript types.

---

## 6. UX/UI Design Guidelines Compliance

### 6.1 Design Token & Color Violations
- **Forbidden Colors**: Emerald/Green colors (`bg-emerald-50`, `text-emerald-700`) are used extensively for "verified" and "complete" statuses, violating the strict "no green" rule.
- **Tailwind Blue Overrides**: Generic `hover:bg-blue-700` and `border-blue-200` are used instead of referencing `var(--royal)` and `var(--royal-hover)`.
- **Hardcoded Hexes**: Components hardcode colors inline (`#4B5563`, `#DC2626`) or as Tailwind extensions (`bg-gradient-to-br from-[#FF6B35]`).

### 6.2 Layout, Borders, & Typography
- **Forbidden Box Shadows**: Non-popover elements like Login cards, Composer inputs, Search triggers, and Document viewers apply `shadow-sm`, `shadow-md`, or `shadow-xl`. 
- **Non-Hairline Borders**: Error pages, GSTR3B tables, and Workspaces use heavy colored borders (e.g., `border-amber-300`) instead of the required hairline (`rgba(0,0,0,0.06)`).
- **Border Radius**: Buttons and cards wildly mix `rounded-lg` (8px), `rounded-xl` (12px), and `rounded-2xl` (16px), ignoring the strict 6px/10px constraint.
- **Data Formatting**: Client IDs, PAN numbers, and amounts are occasionally rendered as standard left-aligned body text instead of right-aligned monospace (`font-mono`).

### 6.3 Route Quality
- **Missing Loading/Error states**: At least 13 active routes lack local `loading.tsx` and `error.tsx` boundary files.
- **Missing Empty States**: Registers and tables often write custom inline placeholders instead of using the central `<EmptyState>` component.
