"""Idempotent purchase-register projection from matched provider verification."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from core.money import rupees_to_paise


def _field(fields: list[dict], *keys: str) -> str:
    return next((str(item.get("value") or "").strip() for item in fields if item.get("key") in keys), "")


def _period(value: str) -> str:
    parsed = datetime.fromisoformat(value[:10])
    return f"{parsed.month:02d}{parsed.year}"


async def project_verified_purchase(conn, action_id: str, verification_id: str) -> str | None:
    """Project exactly one active row; replaying the same snapshot is a no-op."""
    row = await conn.fetchrow(
        """SELECT a.*,d.id AS draft_id,d.document_id,d.totals,d.mappings,
           doc.vendor_name,doc.fields,doc.file_url,v.id AS verification_id,v.status AS verification_status,
           p.id AS provider_object_uuid,p.provider_id,p.snapshot_hash,p.status AS provider_status,p.void
           FROM finance_actions a
           JOIN accounting_drafts d ON d.action_id=a.id
           JOIN documents doc ON doc.id=d.document_id
           JOIN verification_results v ON v.id=$2::uuid AND v.action_id=a.id
           JOIN provider_objects p ON p.id=v.provider_object_id
           WHERE a.id=$1::uuid""", action_id, verification_id,
    )
    if not row or row["verification_status"] != "MATCHED":
        return None
    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"])
    totals = json.loads(row["totals"]) if isinstance(row["totals"], str) else dict(row["totals"])
    fields = json.loads(row["fields"]) if isinstance(row["fields"], str) else list(row["fields"])
    date = str(payload.get("date") or _field(fields, "invoiceDate", "invoice_date"))
    source_identity = f"{row['provider']}:{row['provider_object_uuid']}"
    source_version = str(row["snapshot_hash"])
    register_id = "pr-" + hashlib.sha256(f"{source_identity}:{source_version}".encode()).hexdigest()[:24]
    tax = int(totals.get("tax_paise", payload.get("tax_total_paise", payload.get("tax_paise", 0))) or 0)
    taxable = int(totals.get("taxable_paise", payload.get("subtotal_paise", payload.get("taxable_paise", 0))) or 0)
    cgst = rupees_to_paise(_field(fields, "cgst") or 0)
    sgst = rupees_to_paise(_field(fields, "sgst") or 0)
    igst = rupees_to_paise(_field(fields, "igst") or 0)
    await conn.execute(
        """UPDATE purchase_register SET active=false,superseded_at=NOW()
           WHERE firm_id=$1 AND client_id=$2 AND source_identity=$3 AND source_version<>$4 AND active""",
        row["firm_id"], row["client_id"], source_identity, source_version,
    )
    projected = await conn.fetchrow(
        """INSERT INTO purchase_register(id,firm_id,client_id,period,bill_number,vendor_name,vendor_gstin,
           bill_date,total_paise,tax_total_paise,taxable_paise,cgst_paise,sgst_paise,igst_paise,
           other_charges_paise,source,status,source_identity,source_version,provider,provider_object_id,
           document_id,accounting_draft_id,finance_action_id,verification_id,evidence,active)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8::date,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,
           $22,$23,$24,$25,$26::jsonb,true)
           ON CONFLICT(firm_id,client_id,source_identity,source_version) WHERE source_identity IS NOT NULL
           DO UPDATE SET status=EXCLUDED.status,verification_id=EXCLUDED.verification_id,
             provider_object_id=EXCLUDED.provider_object_id,evidence=EXCLUDED.evidence,active=true,
             superseded_at=NULL,synced_at=NOW() RETURNING id""",
        register_id, row["firm_id"], row["client_id"], _period(date),
        str(payload.get("bill_number") or payload.get("voucher_number") or _field(fields, "invoiceNumber", "invoice_number")),
        row["vendor_name"], _field(fields, "gstin", "vendorGstin", "vendor_gstin"), date,
        int(totals.get("total_paise", payload.get("total_paise", 0))), tax, taxable, cgst, sgst, igst,
        int(totals.get("other_charges_paise", 0)), row["provider"], row["provider_status"],
        source_identity, source_version, row["provider"], row["provider_id"], row["document_id"],
        row["draft_id"], row["id"], row["verification_id"],
        json.dumps([{"kind": "document", "id": row["document_id"]},
                    {"kind": "verification", "id": str(row["verification_id"])}]),
    )
    await conn.execute("UPDATE documents SET status='POSTED',updated_at=NOW() WHERE id=$1", row["document_id"])
    await conn.execute("UPDATE accounting_drafts SET status='POSTED',external_reference_id=$1,updated_at=NOW() WHERE id=$2",
                       row["provider_id"], row["draft_id"])
    return str(projected["id"])
