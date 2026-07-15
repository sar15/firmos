"""Stream API routes — Dashboard feed.

Pulls from decisions + audit_log + recent documents.
Groups by urgency for the decision cockpit.
"""

from fastapi import APIRouter, Depends

from api.deps import get_current_firm, FirmContext, get_db

router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("")
async def get_stream(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db),
):
    """GET /api/stream → returns dashboard events grouped by status."""
    if not db_pool:
        return {"groups": [], "recentActivity": []}

    async with db_pool.acquire() as conn:
        # Decisions — the primary cockpit feed
        decision_rows = await conn.fetch(
            """SELECT d.*, c.legal_name as client_name
               FROM decisions d
               LEFT JOIN clients c ON d.client_id = c.id
               WHERE d.firm_id = $1 AND d.status != 'approved' AND d.status != 'rejected'
               ORDER BY d.created_at DESC""",
            firm.firm_id,
        )

        groups = {
            "BLOCKED": [],
            "NEEDS_REVIEW": [],
            "NEEDS_APPROVAL": [],
        }

        for row in decision_rows:
            urgency = (row["urgency"] or "MEDIUM").upper()
            if urgency == "HIGH":
                group_key = "BLOCKED"
            elif urgency == "MEDIUM":
                group_key = "NEEDS_REVIEW"
            else:
                group_key = "NEEDS_APPROVAL"

            groups[group_key].append({
                "id": row["id"],
                "task": f"{row['flag']} - {row['document_id']}" if row["flag"] else row["document_id"],
                "client": row["client_name"] or "Unknown Client",
                "amount": row["amount"],
                "amountSuffix": "INR",
                "subLine": row.get("recommendation") or "Review required.",
                "dueDate": row["created_at"].isoformat() + "Z",
                "buttonText": "Review →",
                "taskHref": f"/decisions/{row['id']}",
            })

        # Recent activity: audit_log + document uploads
        activity = []

        try:
            audit_rows = await conn.fetch(
                """SELECT action, actor, details, created_at
                   FROM audit_log
                   WHERE firm_id = $1
                   ORDER BY created_at DESC LIMIT 20""",
                firm.firm_id,
            )
            for row in audit_rows:
                activity.append({
                    "type": "audit",
                    "action": row["action"],
                    "actor": row["actor"],
                    "details": row["details"],
                    "timestamp": row["created_at"].isoformat() + "Z",
                })
        except Exception:
            pass  # audit_log table may not exist yet

        try:
            doc_rows = await conn.fetch(
                """SELECT id, client_name, doc_kind, status, vendor_name, uploaded_at
                   FROM documents
                   WHERE firm_id = $1
                   ORDER BY uploaded_at DESC LIMIT 10""",
                firm.firm_id,
            )
            for row in doc_rows:
                activity.append({
                    "type": "document",
                    "action": f"{row['doc_kind']}_{row['status']}",
                    "actor": "firmOS",
                    "details": f"{row['vendor_name'] or 'Unknown'} ({row['client_name']})",
                    "timestamp": row["uploaded_at"].isoformat() + "Z",
                    "documentId": row["id"],
                })
        except Exception:
            pass  # documents table shape may differ

        # Sort activity by timestamp descending
        activity.sort(key=lambda x: x["timestamp"], reverse=True)

        return {
            "groups": [
                {
                    "id": "BLOCKED",
                    "title": "Blocked",
                    "dotColor": "red",
                    "caption": "Cannot proceed without your call",
                    "items": groups["BLOCKED"],
                },
                {
                    "id": "NEEDS_REVIEW",
                    "title": "Needs Review",
                    "dotColor": "amber",
                    "caption": "firmOS prepared a position — verify it",
                    "items": groups["NEEDS_REVIEW"],
                },
                {
                    "id": "NEEDS_APPROVAL",
                    "title": "Needs Approval",
                    "dotColor": "var(--royal)",
                    "caption": "Checks passed — your sign-off files it",
                    "items": groups["NEEDS_APPROVAL"],
                },
            ],
            "recentActivity": activity[:30],
        }
