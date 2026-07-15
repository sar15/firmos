# UI Action Inventory

This is the authoritative inventory for currently rendered interactive controls.
`View` never changes business data. `Draft`, `Review`, `Approve`, `Execute`,
`Import`, `Export`, and `Delete` have the meanings used in the workflow policy.

| Surface | Action | Class | Current status |
|---|---|---|---|
| Authentication | Sign in / sign out | Execute | Enabled; Supabase session is verified before private routes render. |
| Global navigation: `LeftRail`, `SettingsSidebar`, `AppShell` | Navigate or skip to content | View | Enabled; local navigation only. |
| Top bar | Open notifications | View | Enabled. |
| Top bar and not-found page | Open command palette | View | Enabled; local UI event. |
| Command palette and search results | Navigate to a selected result | View | Enabled; route navigation only. |
| Error boundaries | Retry render | View | Enabled; retries the page only. |
| Notifications panel | Open notification / mark all read | Review | Enabled; uses the notification API and fails visibly if unavailable. |
| Agent workspace | Select period | View | Enabled; reloads live context. |
| Agent composer | Choose client mention | View | Enabled; local selection. |
| Agent composer | Insert manual-pack or exception prompt | Draft | Enabled; edits the draft only. |
| Agent composer | Send prompt | Draft | Enabled; submits an agent request for the selected client. |
| Agent plan preview | Inspect sources, dependencies, financial diff, approval and recovery | Review | Enabled; derived from the persistent immutable finance action. |
| Agent exception inbox | Review auth, evidence, mapping, verification and deadline blockers | Review | Enabled; tenant-filtered and ordered by recovery priority. |
| Agent run timeline | Inspect queued through verified completion states | View | Enabled; shows the durable action state and correlation reference. |
| Agent approval card | Approve and queue / reject | Approve | Enabled through `ActionButton`; approval is payload-hash bound and provider execution remains worker-only. |
| Agent OTP card | Portal OTP collection or filing | Execute | Disabled; V1 requires manual government filing. |
| Agent step card | Expand or collapse detail | View | Enabled; local UI only. |
| Documents inbox | Search, filters, and open document | View | Enabled; queries or filters documents. |
| Documents inbox | Select and upload evidence | Import | Enabled; uploads private evidence and fails closed without private storage. |
| Document viewer | Zoom, reset, and render preview | View | Enabled; preview never substitutes a sample document. |
| Document review | Edit extracted field / supplier mappings | Review | Enabled; local review state pending explicit action. |
| Document review | Reject, request information, approve/post | Review / Approve | Enabled; backend controls proposal and execution boundaries. |
| Sales and purchase registers | Choose period, return to client | View | Enabled. |
| Sales and purchase registers | Sync Zoho registers | Import | Enabled; provider read synchronization. |
| GSTR-3B cell | Copy value | View | Enabled; clipboard-only. |
| Reconciliation header | Set period, mode, filters, collapse panel | View | Enabled; local/view state. |
| Reconciliation header and upload card | Upload GSTR-2B or bank statement | Import | Enabled; evidence upload flow. |
| Reconciliation matches | Accept, reject, undo, bulk accept | Review | Enabled; records reconciliation review. |
| Connectors browse/connected tabs and drawer | Browse, filter, open, close, copy bridge command | View | Enabled; copy is local clipboard action. |
| Connector drawer | Start Zoho OAuth / choose organization | Import | Enabled; authenticated connector setup. |
| Connectors list | Connect or manage supported connector | Import | Enabled only for supported flow; unsupported connectors disclose their status. |
| Connectors list | Overflow action menus | View | Disabled; no action implementation exists. |
| Clients list | Search, filter, sort, open client | View | Enabled. |
| Clients list and create modal | Open modal, fill form, create client | Draft / Execute | Enabled; server creates only the firm-scoped client record. |
| Client profile | Open active workflow | View | Enabled; navigates to its review record. |
| Client profile | Compliance dates and filing history | View | Disabled as data surfaces; V1 shows no invented dates, filings, or ARN values. |
| Audit log | Audit export and filters | Export / View | Disabled; no audit filtering or export implementation exists. |
| Billing settings | Plan, usage, payment method, invoice controls | Execute / Export | Disabled; billing is not connected. |
| Profile settings | Edit firm identity | Execute | Disabled; no profile mutation API exists. |
| Security settings | Session revocation and firm deletion | Delete | Disabled; no session or destructive-account API exists. |
| Team settings | Invite member or change role | Execute | Disabled; no team API exists. |

## Guardrails

- A control must not be shown as enabled without a real handler and a classified server boundary.
- A provider write is an `Execute` action only through the finance-action engine and its capability/kill-switch checks.
- Government portal submission, OTP collection, and filing acknowledgement claims are unavailable in V1.
- New interactive controls must be added to this table in the same change.

## Shared action contract

Every new mutating control uses `ActionButton` and declares its capability,
permission, typed mutation, loading label, confirmation policy, correlation
reference, success evidence, and disabled reason. An idempotency key is required
when the mutation creates a logical provider action. Server authorization and
capability checks remain authoritative.
