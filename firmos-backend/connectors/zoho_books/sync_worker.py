"""Durable Zoho master and transaction sync executor."""
import json

from connectors.platform.provider_objects import mark_disappeared, snapshot_hash, upsert_snapshot
from connectors.platform.types import Cursor, ResultStatus, Scope
from connectors.zoho_books.connector import ZohoBooksV1Connector

MASTER_JOBS = {
    "zoho.sync.contacts": "contacts", "zoho.sync.accounts": "accounts",
    "zoho.sync.items": "items", "zoho.sync.taxes": "taxes",
}
TRANSACTION_JOBS = {
    "zoho.sync.purchase_bills": "purchase_bills",
    "zoho.sync.sales_invoices": "sales_invoices",
}
OBJECT_TYPES = {
    "contacts": "contact", "accounts": "account", "items": "item", "taxes": "tax",
    "purchase_bills": "purchase_bill", "sales_invoices": "sales_invoice",
}


def _json(value, default):
    if value is None:
        return default
    return json.loads(value) if isinstance(value, str) else value


async def claim_sync_job(pool, worker_id: str) -> dict | None:
    async with pool.acquire() as conn, conn.transaction():
        row = await conn.fetchrow(
            """SELECT j.* FROM connector_sync_jobs j JOIN connector_installations i
               ON i.id=j.installation_id AND i.status='AVAILABLE'
               WHERE j.status='QUEUED' AND (j.lease_expires_at IS NULL OR j.lease_expires_at<NOW())
               ORDER BY j.created_at FOR UPDATE OF j SKIP LOCKED LIMIT 1""",
        )
        if not row:
            return None
        await conn.execute(
            """UPDATE connector_sync_jobs SET status='RUNNING',lease_owner=$1,
               lease_expires_at=NOW()+interval '60 seconds',started_at=COALESCE(started_at,NOW())
               WHERE id=$2""", worker_id, row["id"],
        )
    return dict(row)


async def run_sync_job(pool, worker_id: str) -> bool:
    job = await claim_sync_job(pool, worker_id)
    if not job:
        return False
    connector = ZohoBooksV1Connector(pool, str(job["installation_id"]))
    cursor = Cursor(job["cursor"])
    if job["capability_key"] in MASTER_JOBS:
        object_type = MASTER_JOBS[job["capability_key"]]
        result = await connector.list_masters(object_type, cursor)
    elif job["capability_key"] in TRANSACTION_JOBS:
        object_type = TRANSACTION_JOBS[job["capability_key"]]
        start, end = _period_bounds(job["period"])
        result = await connector.list_transactions(object_type, Scope(job["client_id"], f"{start}:{end}"), cursor)
    else:
        await _fail(pool, job["id"], "SYNC_KIND_UNSUPPORTED")
        return True
    if result.status not in {ResultStatus.SUCCESS, ResultStatus.PARTIAL, ResultStatus.NO_DATA}:
        await _fail(pool, job["id"], result.reason_code or result.status.value)
        return True

    objects = []
    for item in result.data or []:
        if item.object_type in {"purchase_bill", "sales_invoice"}:
            detail = await connector.get_object(item.object_type, item.provider_id)
            item = detail.data if detail.status is ResultStatus.SUCCESS and detail.data else item
        objects.append(item)
    seen = list(dict.fromkeys([*_json(job.get("seen_provider_ids"), []), *(item.provider_id for item in objects)]))
    async with pool.acquire() as conn, conn.transaction():
        for item in objects:
            object_id, _change = await upsert_snapshot(
                conn, firm_id=job["firm_id"], installation_id=str(job["installation_id"]),
                object_type=item.object_type, provider_id=item.provider_id,
                values=item.values, provider_version=item.provider_version,
                status=str(item.values.get("status") or "ACTIVE"),
                void=str(item.values.get("status") or "").lower() in {"void", "voided"},
            )
            if item.object_type in {"purchase_bill", "sales_invoice"}:
                await _project(conn, job, item, object_id, snapshot_hash(item.values))
                await _project_tax(conn, job, item)
        complete = result.status is not ResultStatus.PARTIAL
        if complete:
            await mark_disappeared(
                conn, firm_id=job["firm_id"], installation_id=str(job["installation_id"]),
                object_type=(objects[0].object_type if objects else OBJECT_TYPES[object_type]),
                seen_provider_ids=seen,
            )
            if object_type in TRANSACTION_JOBS.values():
                table = "purchase_register" if object_type == "purchase_bills" else "sales_register"
                provider_type = "purchase_bill" if object_type == "purchase_bills" else "sales_invoice"
                await conn.execute(
                    f"""UPDATE {table} r SET active=false,status='DISAPPEARED',superseded_at=NOW()
                       FROM provider_objects p WHERE p.firm_id=$1 AND p.installation_id=$2
                       AND p.object_type='{provider_type}' AND p.deleted
                       AND r.source_identity='ZOHO_BOOKS:'||p.id::text AND r.active""",
                    job["firm_id"], job["installation_id"],
                )
        await conn.execute(
            """UPDATE connector_sync_jobs SET status=$1,completeness=$2,cursor=$3,
               processed_count=processed_count+$4,seen_provider_ids=$5::jsonb,
               provider_snapshot_version=$6,lease_owner=NULL,lease_expires_at=NULL,
               finished_at=CASE WHEN $2='COMPLETE' THEN NOW() ELSE NULL END
               WHERE id=$7""",
            "SUCCEEDED" if complete else "QUEUED", "COMPLETE" if complete else "PARTIAL",
            result.next_cursor.value if result.next_cursor else None, len(objects), json.dumps(seen),
            max((item.provider_version or "" for item in objects), default=None), job["id"],
        )
        if complete and object_type in TRANSACTION_JOBS.values():
            await _record_window(conn, job, seen, object_type)
    return True


def _period_bounds(period: str) -> tuple[str, str]:
    month, year = int(period[:2]), int(period[2:])
    start = f"{year:04d}-{month:02d}-01"
    next_month = f"{year + (month == 12):04d}-{1 if month == 12 else month + 1:02d}-01"
    from datetime import date, timedelta
    end = (date.fromisoformat(next_month) - timedelta(days=1)).isoformat()
    return start, end


async def _project(conn, job: dict, item, object_id: str, version: str) -> None:
    values = item.values
    common = [job["firm_id"], job["client_id"], job["period"], item.provider_id]
    if item.object_type == "purchase_bill":
        await conn.execute(
            """UPDATE purchase_register SET active=false,superseded_at=NOW()
               WHERE firm_id=$1 AND client_id=$2 AND source_identity=$3 AND source_version<>$4 AND active""",
            job["firm_id"], job["client_id"], f"ZOHO_BOOKS:{object_id}", version,
        )
        await conn.execute(
            """INSERT INTO purchase_register(id,firm_id,client_id,period,zoho_bill_id,
               bill_number,vendor_name,vendor_gstin,bill_date,total_paise,tax_total_paise,taxable_paise,
               cgst_paise,sgst_paise,igst_paise,source,status,provider,provider_object_id,source_identity,
               source_version,evidence,active)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,'ZOHO',$16,'ZOHO_BOOKS',$17,$18,$19,$20::jsonb,$21)
               ON CONFLICT(firm_id,client_id,source_identity,source_version) WHERE source_identity IS NOT NULL
               DO UPDATE SET status=EXCLUDED.status,active=EXCLUDED.active,synced_at=NOW()""",
            f"zoho-bill-{item.provider_id}-{version[:8]}", *common,
            values.get("bill_number"), values.get("vendor_name"), values.get("vendor_gstin"),
            values.get("date") or None, values.get("total_paise", 0),
            values.get("tax_total_paise", 0), values.get("subtotal_paise", 0),
            sum(int(x.get("cgst_paise", 0)) for x in values.get("line_items", [])),
            sum(int(x.get("sgst_paise", 0)) for x in values.get("line_items", [])),
            sum(int(x.get("igst_paise", 0)) for x in values.get("line_items", [])),
            values.get("status") or "Synced", item.provider_id, f"ZOHO_BOOKS:{object_id}", version,
            json.dumps([{"kind": "provider_object", "id": object_id}]),
            str(values.get("status") or "").lower() not in {"void", "voided"},
        )
        return
    components={key:sum(int(line.get(key,0)) for line in values.get("line_items",[]))
                for key in ("cgst_paise","sgst_paise","igst_paise","cess_paise")}
    identity=f"ZOHO_BOOKS:{object_id}"
    await conn.execute("UPDATE sales_register SET active=false,superseded_at=NOW() WHERE firm_id=$1 AND client_id=$2 AND source_identity=$3 AND source_version<>$4 AND active",job["firm_id"],job["client_id"],identity,version)
    await conn.execute(
        """INSERT INTO sales_register(id,firm_id,client_id,period,zoho_invoice_id,invoice_number,
           customer_name,customer_gstin,place_of_supply,invoice_date,total_paise,tax_total_paise,
           taxable_paise,cgst_paise,sgst_paise,igst_paise,cess_paise,e_invoice,status,provider,
           provider_object_id,source_identity,source_version,evidence,active)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18::jsonb,
           $19,'ZOHO_BOOKS',$20,$21,$22,$23::jsonb,$24)
           ON CONFLICT(firm_id,client_id,source_identity,source_version) WHERE source_identity IS NOT NULL
           DO UPDATE SET status=EXCLUDED.status,active=EXCLUDED.active,synced_at=NOW()""",
        f"zoho-invoice-{item.provider_id}-{version[:8]}",*common,values.get("invoice_number"),
        values.get("customer_name"),values.get("customer_gstin"),values.get("place_of_supply"),
        values.get("date") or None,values.get("total_paise",0),values.get("tax_total_paise",0),
        values.get("subtotal_paise",0),components["cgst_paise"],components["sgst_paise"],
        components["igst_paise"],components["cess_paise"],json.dumps(values.get("e_invoice") or {}),
        values.get("status") or "Synced",item.provider_id,identity,version,
        json.dumps([{"kind":"provider_object","id":object_id}]),
        str(values.get("status") or "").lower() not in {"void","voided"},
    )


async def _project_tax(conn, job: dict, item) -> None:
    values = item.values
    lines = values.get("line_items", [])
    components = {
        key: sum(int(line.get(key, 0)) for line in lines)
        for key in ("igst_paise", "cgst_paise", "sgst_paise", "cess_paise")
    }
    component_total = sum(components.values())
    await conn.execute(
        """INSERT INTO gst_tax_components(firm_id,client_id,period,source_type,source_id,
           taxable_paise,igst_paise,cgst_paise,sgst_paise,cess_paise,components_verified,
           itc_eligible,source_snapshot)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,NULL,$12::jsonb)
           ON CONFLICT(firm_id,client_id,source_type,source_id) DO UPDATE SET
           period=EXCLUDED.period,taxable_paise=EXCLUDED.taxable_paise,
           igst_paise=EXCLUDED.igst_paise,cgst_paise=EXCLUDED.cgst_paise,
           sgst_paise=EXCLUDED.sgst_paise,cess_paise=EXCLUDED.cess_paise,
           components_verified=EXCLUDED.components_verified,
           source_snapshot=EXCLUDED.source_snapshot,synced_at=NOW()""",
        job["firm_id"], job["client_id"], job["period"],
        "PURCHASE" if item.object_type == "purchase_bill" else "SALES", item.provider_id,
        values.get("subtotal_paise", 0), components["igst_paise"], components["cgst_paise"],
        components["sgst_paise"], components["cess_paise"],
        component_total == int(values.get("tax_total_paise", 0)), json.dumps(values),
    )


async def _record_window(conn, job: dict, seen: list[str], object_type: str) -> None:
    purchase=object_type=="purchase_bills"
    provider_type="purchase_bill" if purchase else "sales_invoice"
    table="purchase_register" if purchase else "sales_register"
    expected = await conn.fetchrow(
        f"""SELECT COUNT(*) AS count,COALESCE(SUM((snapshot->>'subtotal_paise')::bigint),0) AS taxable,
           COALESCE(SUM((snapshot->>'tax_total_paise')::bigint),0) AS tax,
           COALESCE(SUM((snapshot->>'total_paise')::bigint),0) AS total
           FROM provider_objects WHERE firm_id=$1 AND installation_id=$2 AND object_type='{provider_type}'
           AND provider_id=ANY($3::text[]) AND active""", job["firm_id"], job["installation_id"], seen,
    )
    projected = await conn.fetchrow(
        f"""SELECT COUNT(*) AS count,COALESCE(SUM(taxable_paise),0) AS taxable,
           COALESCE(SUM(tax_total_paise),0) AS tax,COALESCE(SUM(total_paise),0) AS total
           FROM {table} WHERE firm_id=$1 AND client_id=$2 AND period=$3
           AND provider='ZOHO_BOOKS' AND active""", job["firm_id"], job["client_id"], job["period"],
    )
    expected_totals = {key: int(expected[key]) for key in ("taxable", "tax", "total")}
    projected_totals = {key: int(projected[key]) for key in ("taxable", "tax", "total")}
    state = "COMPLETE" if int(expected["count"]) == int(projected["count"]) and expected_totals == projected_totals else "MISMATCH"
    register_type="PURCHASE" if purchase else "SALES"
    await conn.execute(
        f"""INSERT INTO register_sync_windows(firm_id,client_id,provider,register_type,period,state,
           expected_count,processed_count,expected_totals,processed_totals,complete_through)
           VALUES($1,$2,'ZOHO_BOOKS','{register_type}',$3,$4,$5,$6,$7::jsonb,$8::jsonb,
           CASE WHEN $4='COMPLETE' THEN NOW() ELSE NULL END)
           ON CONFLICT(firm_id,client_id,provider,register_type,period) DO UPDATE SET state=EXCLUDED.state,
           expected_count=EXCLUDED.expected_count,processed_count=EXCLUDED.processed_count,
           expected_totals=EXCLUDED.expected_totals,processed_totals=EXCLUDED.processed_totals,
           complete_through=EXCLUDED.complete_through,updated_at=NOW()""",
        job["firm_id"], job["client_id"], job["period"], state, int(expected["count"]),
        int(projected["count"]), json.dumps(expected_totals), json.dumps(projected_totals),
    )


async def _fail(pool, job_id, code: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE connector_sync_jobs SET status='FAILED',mapping_blockers=$1::jsonb,
               lease_owner=NULL,lease_expires_at=NULL,finished_at=NOW() WHERE id=$2""",
            json.dumps([code]), job_id,
        )
