"""Project matched sales verifications into one active canonical register row."""
import hashlib
import json
from datetime import datetime

from core.money import rupees_to_paise


def _field(fields: list[dict], *keys: str) -> str:
    return next((str(item.get("value") or "").strip() for item in fields if item.get("key") in keys), "")


async def project_verified_sale(conn, action_id: str, verification_id: str) -> str | None:
    row = await conn.fetchrow(
        """SELECT a.*,d.id draft_id,d.document_id,d.totals,doc.vendor_name,doc.fields,
           v.id verification_id,v.status verification_status,p.id provider_object_uuid,
           p.provider_id,p.snapshot_hash,p.status provider_status,p.snapshot
           FROM finance_actions a JOIN accounting_drafts d ON d.action_id=a.id
           JOIN documents doc ON doc.id=d.document_id
           JOIN verification_results v ON v.id=$2::uuid AND v.action_id=a.id
           JOIN provider_objects p ON p.id=v.provider_object_id WHERE a.id=$1::uuid""",
        action_id, verification_id,
    )
    if not row or row["verification_status"] != "MATCHED":
        return None
    payload = json.loads(row["payload"]) if isinstance(row["payload"], str) else dict(row["payload"])
    totals = json.loads(row["totals"]) if isinstance(row["totals"], str) else dict(row["totals"])
    fields = json.loads(row["fields"]) if isinstance(row["fields"], str) else list(row["fields"])
    snapshot = json.loads(row["snapshot"]) if isinstance(row["snapshot"], str) else dict(row["snapshot"])
    invoice_date = str(payload.get("date") or _field(fields, "invoiceDate", "invoice_date"))
    parsed = datetime.fromisoformat(invoice_date[:10])
    identity, version = f"{row['provider']}:{row['provider_object_uuid']}", str(row["snapshot_hash"])
    register_id = "sr-" + hashlib.sha256(f"{identity}:{version}".encode()).hexdigest()[:24]
    await conn.execute(
        "UPDATE sales_register SET active=false,superseded_at=NOW() WHERE firm_id=$1 AND client_id=$2 AND source_identity=$3 AND source_version<>$4 AND active",
        row["firm_id"], row["client_id"], identity, version,
    )
    projected = await conn.fetchrow(
        """INSERT INTO sales_register(id,firm_id,client_id,period,invoice_number,customer_name,
           customer_gstin,invoice_date,place_of_supply,total_paise,tax_total_paise,taxable_paise,
           cgst_paise,sgst_paise,igst_paise,cess_paise,e_invoice,status,source_identity,source_version,
           provider,provider_object_id,document_id,accounting_draft_id,finance_action_id,verification_id,evidence,active)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8::date,$9,$10,$11,$12,$13,$14,$15,$16,$17::jsonb,$18,$19,$20,
             $21,$22,$23,$24,$25,$26,$27::jsonb,true)
           ON CONFLICT(firm_id,client_id,source_identity,source_version) WHERE source_identity IS NOT NULL
           DO UPDATE SET status=EXCLUDED.status,verification_id=EXCLUDED.verification_id,evidence=EXCLUDED.evidence,
             active=true,superseded_at=NULL,synced_at=NOW() RETURNING id""",
        register_id,row["firm_id"],row["client_id"],f"{parsed.month:02d}{parsed.year}",
        payload.get("invoice_number"),snapshot.get("customer_name") or row["vendor_name"],
        snapshot.get("customer_gstin") or _field(fields,"customerGstin","gstin"),invoice_date,
        payload.get("place_of_supply"),int(totals.get("total_paise",payload.get("total_paise",0))),
        int(totals.get("tax_paise",payload.get("tax_total_paise",0))),int(totals.get("taxable_paise",payload.get("subtotal_paise",0))),
        rupees_to_paise(_field(fields,"cgst") or 0),rupees_to_paise(_field(fields,"sgst") or 0),
        rupees_to_paise(_field(fields,"igst") or 0),rupees_to_paise(_field(fields,"cess") or 0),
        json.dumps(snapshot.get("e_invoice") or {}),row["provider_status"],identity,version,row["provider"],
        row["provider_id"],row["document_id"],row["draft_id"],row["id"],row["verification_id"],
        json.dumps([{"kind":"document","id":row["document_id"]},{"kind":"verification","id":str(row["verification_id"])}]),
    )
    await conn.execute("UPDATE documents SET status='POSTED',updated_at=NOW() WHERE id=$1",row["document_id"])
    await conn.execute("UPDATE accounting_drafts SET status='POSTED',external_reference_id=$1,updated_at=NOW() WHERE id=$2",row["provider_id"],row["draft_id"])
    return str(projected["id"])
