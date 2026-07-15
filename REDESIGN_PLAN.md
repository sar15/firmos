# firmOS Frontend Redesign — Execution Plan

**Version:** 1.0 · Final
**Author:** Design + Engineering review
**Status:** Ready for execution
**Scope:** Reskin the existing Next.js frontend into the Cursor-style chat-first surface (design-sample-v6), without rebuilding the backend.

---

## 0. Guiding Principle

> **The backend is done. The design system is done. This plan only reorganizes how the frontend renders existing backend data.**

Every step card in the new UI is a rendered `audit_entry` from `workflows/graphs.py`. Every approval is an `interrupt()` resume. Every document is a row in the `documents` table. **No new backend logic is required for the core redesign** — only one new read-only endpoint (`/api/chat/session`) and one new table (`chat_messages`).

If a task in this plan requires new backend logic, it is explicitly marked **[BACKEND]** and deferred. Do not expand backend scope during the frontend redesign.

---

## 1. Current State (verified)

### What exists and works
- **Backend:** FastAPI + LangGraph, 99/100 tests passing, real deterministic engines, real Supabase JWT auth, real WhiteBooks GSP integration, two-step EVC OTP filing flow, immutable audit log.
- **Frontend (`apps/web`):** Next.js 16 + React 19, ~7,300 LOC across 25+ routes. Design tokens in `globals.css` already match the vision (royal `#2540D9`, hairlines, mono numbers). Wired to backend via `next.config.ts` rewrites + per-feature `.api.ts` files.
- **Design sample:** `design-sample-v6.html` — 3-pane Cursor-style structure, validated.

### What's wrong with the current frontend
1. **Fragmented IA:** 5+ separate routes (`/clients`, `/decisions`, `/run/[id]`, `/reconcile`, `/documents`) — each a table or form. The CA context-switches constantly. No unified surface.
2. **Not agentic:** The "run" page shows a terminal-style log. It doesn't *feel* like an agent working — it feels like reading a build log.
3. **Approval friction:** The decision inbox is a 3-pane table. Approving a filing means: open inbox → select decision → review detail → find approve button → click. Should be: see it in chat → approve inline.
4. **No conversation:** There's no way to *ask* firmOS anything. Every action is a click into a siloed page.

---

## 2. Target Architecture

### Three surfaces, one mental model

```
┌─────────┬──────────────────────────┬──────────┐
│  RAIL   │       CHAT (center)      │ CONTEXT  │
│         │                          │  (right) │
│ Agent   │  Greeting + stat chips   │ Client   │
│ Clients │  Agent message           │ focus    │
│ Approvals│   └─ step cards         │          │
│ Recon   │   └─ document preview    │ Needs    │
│ Docs    │   └─ approval card       │ you      │
│         │  Composer (persistent)   │          │
│ ———     │                          │ Filed    │
│ Connect │                          │ today    │
│ Audit   │                          │          │
│ Settings│                          │          │
└─────────┴──────────────────────────┴──────────┘
```

### The unifying data model

Every agent action produces an **audit_entry**. In the new UI:

| Backend concept | UI rendering |
|---|---|
| `audit_entry` (from workflow node) | **Step card** — icon + title + expandable detail |
| `action_proposal` at `interrupt()` | **Approval card** — blue, inline, yes/no |
| `document` with `extracted_data` | **Document preview** — thumbnail + extracted fields |
| `audit_entry.action=PORTAL_SUBMITTED` | **Filed card** — green, ARN, timestamp |
| workflow `status=AWAITING_OTP` | **OTP card** — amber, 6-box input, countdown |

The chat is not a "feature." It is the **rendering layer for the audit log**, presented chronologically with interactivity at the interrupt points.

---

## 3. Execution Plan — 5 Phases

### Phase 0 — Scaffold (Day 1, ~3 hours)

**Goal:** Create the new chat route alongside existing routes. Nothing breaks.

**Files to create:**
```
apps/web/src/app/(app)/agent/page.tsx          ← new chat home
apps/web/src/app/(app)/agent/layout.tsx        ← 3-pane shell
apps/web/src/features/agent/
  ├── AgentChat.tsx                             ← message stream
  ├── AgentComposer.tsx                         ← persistent input
  ├── StepCard.tsx                              ← renders one audit_entry
  ├── ApprovalCard.tsx                          ← renders interrupt() proposal
  ├── OtpCard.tsx                               ← renders AWAITING_OTP state
  ├── FiledCard.tsx                             ← renders filed confirmation
  ├── DocumentPreview.tsx                       ← inline bill/invoice preview
  ├── ChatGreeting.tsx                          ← morning glance + stat chips
  └── agent.api.ts                              ← chat session + workflow subscribe
apps/web/src/features/context/
  ├── ContextColumn.tsx                          ← right pane container
  ├── ClientFocusCard.tsx
  └── NeedsYouList.tsx
```

**Files to modify:**
```
apps/web/src/components/AppShell.tsx            ← add "Agent" to rail as primary
```

**What to do:**
1. Copy the structure from `design-sample-v6.html` into React components.
2. Use the **existing design tokens** from `globals.css` — do NOT redefine colors, radii, shadows.
3. Wire `AgentChat` to read from a static array first (hardcoded messages) — prove the layout renders.
4. Make `/agent` the default redirect from `/`.

**What NOT to do:**
- ❌ Do NOT delete or modify any existing route yet. They stay functional.
- ❌ Do NOT touch `globals.css`. The tokens are correct.
- ❌ Do NOT build the real chat API yet. Mock data only in Phase 0.
- ❌ Do NOT add new dependencies. Use what's in `package.json`.

**Exit criteria:** `/agent` renders the 3-pane layout with mock data, looks like v6, dark mode works, mobile collapses.

---

### Phase 1 — Step Cards + Real Workflow Data (Day 2–3, ~8 hours)

**Goal:** Render real workflow runs as step cards in the chat. Replace the `/run/[id]` terminal log with the chat timeline.

**[BACKEND — minimal, ~2 hours]:**
```
firmos-backend/api/routes/chat.py               ← NEW: GET /api/chat/session
firmos-backend/supabase/migrations/
  └── 20260708000001_chat_messages.sql          ← NEW: chat_messages table
```

The chat session endpoint returns a merged timeline of:
- `chat_messages` (user asks + agent replies)
- `audit_entries` from active/recent workflows (rendered as step cards)
- `action_proposals` at `interrupt()` (rendered as approval cards)

```python
# api/routes/chat.py — shape only
@router.get("/api/chat/session/{client_id}")
async def get_chat_session(client_id, firm, db_pool):
    """Returns a unified timeline:
    - recent chat_messages
    - audit_entries from workflows for this client
    - pending action_proposals (interrupt points)
    Sorted chronologically. The frontend renders each item by type.
    """
```

**SQL migration:**
```sql
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firm_id VARCHAR(255) NOT NULL,
    client_id VARCHAR(50),
    role VARCHAR(20) NOT NULL,  -- user | agent
    text TEXT NOT NULL,
    attached_workflow_id VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
-- standard firm-isolation policies
```

**Files to modify (frontend):**
```
apps/web/src/features/agent/agent.api.ts        ← fetch /api/chat/session
apps/web/src/features/agent/AgentChat.tsx       ← map timeline → components
apps/web/src/features/agent/StepCard.tsx        ← render audit_entry
apps/web/src/features/agent/ApprovalCard.tsx    ← render action_proposal, wire to /api/workflows/t4/resume
```

**Step card rendering rule:**
```tsx
// StepCard maps an audit_entry to a visual step
function StepCard({ entry }: { entry: AuditEntry }) {
  const icon = {
    STEP_COMPLETED: "done",      // ✓ green
    DOCUMENT_EXTRACTED: "done",
    HUMAN_APPROVED: "done",
    PORTAL_SUBMITTED: "done",
    STEP_FAILED: "err",          // ✗ red
  }[entry.action] ?? "done";

  return (
    <div className="step">
      <StepIcon variant={icon} />
      <div className="step-body">
        <div className="step-title">{entry.description}</div>
        {entry.details && <ExpandableDetail data={entry.details} />}
      </div>
    </div>
  );
}
```

**What to do:**
1. Build `/api/chat/session` — it's a JOIN + sort, no new logic.
2. In `AgentChat`, fetch the session and render items by type.
3. Wire `ApprovalCard` to the existing `/api/workflows/{id}/resume` endpoint (already works).
4. Test: trigger a vendor-bill workflow via API → see it appear as step cards in the chat.

**What NOT to do:**
- ❌ Do NOT put business logic in the chat endpoint. It reads; it does not compute.
- ❌ Do NOT render audit_entries differently from chat messages. They share the same timeline. The visual difference (step card vs. bubble) communicates type.
- ❌ Do NOT auto-scroll aggressively. Scroll only on new message if user is already at bottom.
- ❌ Do NOT poll faster than every 5 seconds. Use the existing workflow state endpoint; don't create a new polling pattern.

**Exit criteria:** A real vendor-bill workflow, triggered via API, appears as step cards in `/agent`. Clicking "Post bill" resumes the workflow and a new step card appears.

---

### Phase 2 — The Approval Flows (Day 4–5, ~8 hours)

**Goal:** Both real workflows (vendor bill + GSTR-3B filing) complete end-to-end from the chat, including the two-step OTP.

**Files to modify:**
```
apps/web/src/features/agent/OtpCard.tsx         ← render AWAITING_OTP, wire to /api/workflows/t4/resume
apps/web/src/features/agent/ApprovalCard.tsx    ← detect workflow_type, show right fields
apps/web/src/features/agent/FiledCard.tsx       ← render FILED state with ARN
apps/web/src/features/agent/DocumentPreview.tsx ← render extracted_data inline
```

**Approval card branching:**
```tsx
function ApprovalCard({ proposal }) {
  if (proposal.workflow_type === "VENDOR_BILL") {
    return <BillApproval proposal={proposal} />;       // Post bill? [Post] [Edit] [Reject]
  }
  if (proposal.workflow_type === "GSTR_3B") {
    return <FilingApproval proposal={proposal} />;     // Approve ₹X? [Approve] [Evidence] [Reject]
  }
}
```

**OTP card** reads `workflow.status === "AWAITING_OTP"` from the session timeline and renders the 6-box input. On submit, calls:
```ts
fetch(`/api/workflows/t4/resume`, {
  method: "POST",
  body: JSON.stringify({ thread_id, approval_data: { evc_otp } })
});
```

**What to do:**
1. Make `ApprovalCard` handle both workflow types (vendor bill + GSTR-3B).
2. Make `OtpCard` appear when the timeline shows `AWAITING_OTP`.
3. Make `FiledCard` appear when `PORTAL_SUBMITTED` audit entry lands.
4. Test the full chain: upload bill → extract → approve → post. Then: trigger GSTR-3B → reconcile → approve → OTP → filed.

**What NOT to do:**
- ❌ Do NOT block the UI during workflow execution. Step cards update asynchronously via polling. The CA can scroll and read while the agent works.
- ❌ Do NOT put the OTP input on the approval card. It's a separate state — the approval triggers the OTP request, then the OTP card appears. Two actions, two cards.
- ❌ Do NOT validate OTP format client-side beyond "6 digits." The GSP validates it. Don't fake-validate.
- ❌ Do NOT show raw JSON from the GSP in the UI. Parse it into the step card title + detail.

**Exit criteria:** Both workflows complete from `/agent` without visiting any other route. The CA sees: step cards → approval → (OTP) → filed — all in one scroll.

---

### Phase 3 — Context Column + Composer (Day 6, ~5 hours)

**Goal:** The right column shows live status; the composer lets the CA type commands.

**Files to modify:**
```
apps/web/src/features/context/ContextColumn.tsx     ← fetch needs-you + filed-today
apps/web/src/features/context/ClientFocusCard.tsx   ← current client stats
apps/web/src/features/agent/AgentComposer.tsx       ← POST /api/chat/session, @-mentions
```

**Composer behavior:**
- Free text → POST to `/api/chat/session` as `{role: "user", text}`.
- The backend does NOT process this with an LLM (yet). It pattern-matches:
  - "file gstr-3b for @acme" → triggers `POST /api/workflows/t4/run`
  - "file the 25 clean drafts" → triggers bulk run (Phase 2 P1 feature)
  - "what is overdue" → returns a text summary from compliance_calendar
- If no pattern matches → agent replies "I didn't understand that. Try: file GSTR-3B for [client], or click a suggestion."
- **No hallucinated answers.** Honest "I can't do that yet" beats a confident lie.

**What to do:**
1. Wire `ContextColumn` to existing endpoints (`/api/decisions`, `/api/audit`).
2. Build `@-mention` autocomplete for clients (reuse `listClients`).
3. Build the pattern-matcher in the backend chat endpoint (10–15 rules, not an LLM).

**What NOT to do:**
- ❌ Do NOT wire an LLM to the composer yet. Pattern matching is more reliable, faster, cheaper, and honest. An LLM that says "I've filed your return" when it hasn't is a trust-destroying bug. Add LLM later, behind the pattern-matcher, only for drafting natural-language summaries of deterministic results.
- ❌ Do NOT make the composer the only way to do things. The stat chips and context column items must be clickable shortcuts. The composer is for power users; clicks are for everyone.
- ❌ Do NOT auto-send on @-mention selection. Let the CA finish typing and hit Enter.

**Exit criteria:** CA can type "file gstr-3b for @acme" and the workflow starts, appearing as step cards. The context column updates in real time.

---

### Phase 4 — Route Consolidation + Cleanup (Day 7–8, ~6 hours)

**Goal:** Old routes redirect into the chat. The app has one primary surface.

**Files to modify:**
```
apps/web/src/app/(app)/page.tsx                  ← redirect to /agent
apps/web/src/app/(app)/decisions/page.tsx        ← redirect to /agent (decisions render as approval cards)
apps/web/src/app/(app)/run/[id]/page.tsx         ← redirect to /agent?workflow=id
apps/web/src/app/(app)/clients/page.tsx          ← KEEP (list view is still useful)
apps/web/src/app/(app)/clients/[id]/page.tsx     ← KEEP (client detail)
apps/web/src/app/(app)/reconcile/[clientId]/page.tsx  ← KEEP (match grid is a power tool)
apps/web/src/app/(app)/connectors/page.tsx       ← KEEP
apps/web/src/app/(app)/audit/page.tsx            ← KEEP
```

**What to do:**
1. Make `/` redirect to `/agent`.
2. Make `/decisions` redirect to `/agent` (approval cards replace the decision table).
3. Make `/run/[id]` redirect to `/agent?workflow=[id]` (the chat shows the run inline).
4. Keep `/clients`, `/reconcile`, `/connectors`, `/audit` as secondary surfaces — they're power tools, not the daily driver.
5. Delete the old `DecisionQueue`, `DecisionDetail`, `ContextPanel` components only after confirming nothing references them.

**What NOT to do:**
- ❌ Do NOT delete `/clients`, `/reconcile`, `/connectors`, `/audit`. They serve real purposes (data-dense views the chat doesn't replace). The chat is the default; these are drill-downs.
- ❌ Do NOT force every interaction through the chat. The reconcile match grid, the audit log filter, the client list — these are better as full pages. The chat is for the *workflow*, not for *data browsing*.
- ❌ Do NOT do a big-bang deploy. Ship Phase 0–3 first (new surface working alongside old). Do the redirects in Phase 4 only after the chat is proven.

**Exit criteria:** `/` loads the chat. Old routes either redirect or remain as power tools. No dead links.

---

## 4. What NOT to Do (Anti-Patterns)

These are the mistakes that will kill trust, waste time, or create technical debt. Read this section twice.

### Architecture anti-patterns

1. **❌ Do not use an LLM for the composer's command parsing.**
   Pattern matching is more reliable. An LLM that misinterprets "file 3B for Acme" and files for the wrong client is a catastrophic trust failure. Deterministic parsing for deterministic actions.

2. **❌ Do not compute tax or GST in the frontend.**
   The deterministic engines live in `engines/*.py`. The frontend renders their output. Never recompute. Never round. Display exactly what the engine returned, in paise, formatted as rupees.

3. **❌ Do not create a new polling mechanism.**
   The app already has `getRunExecution()` polling `/api/workflows/{id}/run/{thread_id}`. Reuse it. One polling pattern, 5-second interval, shared across the chat.

4. **❌ Do not build a separate "notifications" system.**
   Notifications are just `chat_messages` with `role=agent` that haven't been seen. One table, one timeline. The bell icon surfaces unread count; clicking opens the chat scrolled to the message.

5. **❌ Do not put the OTP on the approval screen.**
   Filing is two actions: (1) approve the draft, (2) enter the OTP after GSTN sends it. The OTP doesn't exist at approval time. Two cards, two interrupts — that's how the backend works (`t4_approve_gate` → `t4_request_otp` → `t4_otp_gate`).

### Design anti-patterns

6. **❌ Do not use red for anything except compliance urgency.**
   Red means "overdue / failed / rejected." Never use it for primary actions, never for decoration. The "calm, not anxious" principle is your differentiator. One decorative red badge undoes it.

7. **❌ Do not use cards/shadows for structural layout.**
   Hairlines (`1px solid var(--hairline)`) divide sections. Shadows are reserved for raised surfaces (hover states, modals, the composer). A shadow on every container makes the UI feel heavy and consumer-y.

8. **❌ Do not mix mono and sans for the same data type.**
   Money is always mono. Dates are always mono. IDs (PAN, GSTIN, invoice numbers) are always mono. Names, descriptions, and prose are always sans. Inconsistency here makes the UI feel amateur.

9. **❌ Do not animate things that don't need animation.**
   Step icons animate (spinner → ✓) because they communicate state. Approvals don't bounce in. OTP boxes don't shake on error. Motion communicates state change; it's not decoration.

10. **❌ Do not show raw API responses or technical terms.**
    The CA sees "Fetched GSTR-2B (142 invoices)," not `GET /taxpayerapi/v2.0/returns/gstr2b 200 OK`. The step card title is plain English; the expandable detail shows the mono evidence only when the CA asks for it.

### Process anti-patterns

11. **❌ Do not redesign the design system.**
    The tokens in `globals.css` are correct (`--royal: #2540D9`, hairlines, mono numbers, calm grays). Build components that use them. Do not introduce new colors, new radii, or new font sizes.

12. **❌ Do not touch the backend engines.**
    `engines/tax.py`, `engines/gst.py`, `engines/reconcile.py` are tested and correct. The frontend redesign does not modify them. If you find yourself editing an engine file, stop — you're scope-creeping.

13. **❌ Do not ship without dark mode working.**
    Dark mode is not optional. Many CAs work late on the 20th of the month. Every new component must be tested in both themes. The token system makes this automatic — but only if you use tokens, not hardcoded colors.

14. **❌ Do not skip mobile.**
    CAs approve filings from their phones. The 3-pane collapses to 1-pane on mobile: rail becomes a hamburger, context column hides, chat + composer stay. Test every flow at 375px width.

15. **❌ Do not fake success states.**
    If the GSP is down (AUTH403), the step card shows an error, not a fake ✓. If the OTP is wrong, the OTP card shows an error, not a fake "filed." The entire product is trust. One faked success destroys it permanently for that CA.

---

## 5. File Inventory — Complete

### New files (create)

| File | Purpose | Phase |
|---|---|---|
| `apps/web/src/app/(app)/agent/page.tsx` | Chat home route | 0 |
| `apps/web/src/app/(app)/agent/layout.tsx` | 3-pane shell | 0 |
| `apps/web/src/features/agent/AgentChat.tsx` | Message stream | 0 |
| `apps/web/src/features/agent/AgentComposer.tsx` | Persistent input | 0 |
| `apps/web/src/features/agent/StepCard.tsx` | Renders audit_entry | 1 |
| `apps/web/src/features/agent/ApprovalCard.tsx` | Renders interrupt proposal | 2 |
| `apps/web/src/features/agent/OtpCard.tsx` | Renders AWAITING_OTP | 2 |
| `apps/web/src/features/agent/FiledCard.tsx` | Renders filed confirmation | 2 |
| `apps/web/src/features/agent/DocumentPreview.tsx` | Inline bill/invoice | 2 |
| `apps/web/src/features/agent/ChatGreeting.tsx` | Morning glance + stats | 0 |
| `apps/web/src/features/agent/agent.api.ts` | Chat session API | 1 |
| `apps/web/src/features/context/ContextColumn.tsx` | Right pane | 3 |
| `apps/web/src/features/context/ClientFocusCard.tsx` | Client stats | 3 |
| `apps/web/src/features/context/NeedsYouList.tsx` | Pending items | 3 |
| `firmos-backend/api/routes/chat.py` | Chat session endpoint | 1 |
| `supabase/migrations/20260708000001_chat_messages.sql` | Chat table | 1 |

### Modified files (edit)

| File | Change | Phase |
|---|---|---|
| `apps/web/src/components/AppShell.tsx` | Add "Agent" as primary nav | 0 |
| `apps/web/src/app/(app)/page.tsx` | Redirect to /agent | 4 |
| `apps/web/src/app/(app)/decisions/page.tsx` | Redirect to /agent | 4 |
| `apps/web/src/app/(app)/run/[id]/page.tsx` | Redirect to /agent?workflow=id | 4 |
| `apps/web/src/components/LeftRail.tsx` | Update labels (Agent, Approvals) | 0 |
| `apps/web/src/app/(app)/layout.tsx` | Ensure shell wraps agent route | 0 |

### Kept unchanged (do not touch)

| File | Why |
|---|---|
| `apps/web/src/app/globals.css` | Design tokens are correct |
| `apps/web/src/app/(app)/clients/page.tsx` | List view is a power tool |
| `apps/web/src/app/(app)/clients/[id]/page.tsx` | Client detail is useful |
| `apps/web/src/app/(app)/reconcile/*` | Match grid is a power tool |
| `apps/web/src/app/(app)/connectors/*` | Marketplace is correct |
| `apps/web/src/app/(app)/audit/*` | Audit log is correct |
| `firmos-backend/engines/*` | Crown jewels — do not touch |
| `firmos-backend/workflows/graphs.py` | Workflow logic is correct |

### Deleted (Phase 4 only, after verification)

| File | Why |
|---|---|
| `apps/web/src/features/decisions/components/DecisionQueue.tsx` | Replaced by chat timeline |
| `apps/web/src/features/decisions/components/DecisionDetail.tsx` | Replaced by approval card |
| `apps/web/src/features/decisions/components/ContextPanel.tsx` | Replaced by context column |
| `apps/web/src/features/run/components/ActivityLog.tsx` | Replaced by step cards |

---

## 6. Timeline + Effort

| Phase | Duration | Effort | Dependency |
|---|---|---|---|
| **0 — Scaffold** | Day 1 | 3 hrs | None |
| **1 — Step Cards + Real Data** | Day 2–3 | 8 hrs (incl. 2 hrs backend) | Phase 0 |
| **2 — Approval Flows** | Day 4–5 | 8 hrs | Phase 1 |
| **3 — Context + Composer** | Day 6 | 5 hrs (incl. 2 hrs backend) | Phase 2 |
| **4 — Route Consolidation** | Day 7–8 | 6 hrs | Phase 3 |
| **Total** | **8 days** | **~30 hours** | Sequential |

This is one focused week for a single developer. No new dependencies. No backend rewrites. One new table, one new endpoint.

---

## 7. Success Criteria

The redesign is complete when:

1. ✅ A CA can complete a vendor-bill workflow (WhatsApp → extract → approve → Zoho post) entirely from `/agent`, without visiting another route.
2. ✅ A CA can complete a GSTR-3B filing (reconcile → approve → OTP → ARN) entirely from `/agent`.
3. ✅ Every step card traces to a real `audit_entry` in the database.
4. ✅ The context column shows live "needs you" and "filed today" from real data.
5. ✅ Dark mode works on every component.
6. ✅ Mobile (375px) renders the chat + composer usable.
7. ✅ Old routes (`/decisions`, `/run/[id]`) redirect to `/agent` without dead links.
8. ✅ No faked success states anywhere in the UI.

---

## 8. Open Decisions (need your call before Phase 1)

1. **Composer intelligence:** Pattern-matcher only (recommended for pilot), or pattern-matcher + Sarvam LLM for natural-language summarization of deterministic results? (LLM drafts the reply text; it never decides actions.)

2. **Context column client scope:** Show data for the *currently focused client* (via the client switcher), or *all clients across the firm*? (Focused is cleaner; all-clients is more useful for the morning glance.)

3. **Bulk approve:** The "File 25 clean drafts" chip — build it in Phase 3, or defer to post-pilot? (The backend supports it via multiple `/resume` calls; the UI needs a multi-select + confirmation.)

---

## 9. The One Sentence

**The chat is not a chatbot — it is the audit log, rendered as a living timeline, with interactivity at the points where a human must decide. Build that, and firmOS feels like the Cursor of finance.**
