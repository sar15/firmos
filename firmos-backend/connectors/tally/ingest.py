"""Canonical persistence for device-authenticated Tally snapshots."""
from decimal import Decimal
import json

from connectors.platform.provider_objects import snapshot_hash, upsert_snapshot


def period_for(tally_date: str) -> str:
    if len(tally_date) != 8 or not tally_date.isdigit():
        raise ValueError("Tally voucher date must be YYYYMMDD")
    return f"{tally_date[4:6]}{tally_date[:4]}"


def voucher_total(entries: list[dict]) -> int:
    amounts = [abs(int(entry.get("amount_paise", 0))) for entry in entries]
    return max(amounts, default=0)


async def ingest_snapshot(conn, device, payload: dict) -> tuple[int, int]:
    ledgers, vouchers = payload.get("ledgers", []), payload.get("vouchers", [])
    for ledger in ledgers:
        values = {
            "company_guid": device.company_guid, "name": ledger["name"],
            "parent_group": ledger["parent_group"],
            "opening_paise": int(ledger.get("opening_paise", 0)),
            "closing_paise": int(ledger.get("closing_paise", 0)),
            "active": bool(ledger.get("active", True)),
            "gstin": str(ledger.get("gstin") or ""),
            "tax_type": str(ledger.get("tax_type") or ""),
        }
        await upsert_snapshot(
            conn, firm_id=device.firm_id, installation_id=device.installation_id,
            object_type="tally_ledger", provider_id=ledger["guid"], values=values,
            status="ACTIVE" if values["active"] else "INACTIVE", void=not values["active"],
        )
        await conn.execute(
            """INSERT INTO tally_ledgers(firm_id,client_id,installation_id,company_name,
               company_guid,tally_guid,name,parent_group,opening_balance,closing_balance,
               opening_paise,closing_paise,is_revenue,active,gstin,tax_type,synced_at)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,NOW())
               ON CONFLICT(firm_id,tally_guid) DO UPDATE SET name=EXCLUDED.name,
               parent_group=EXCLUDED.parent_group,opening_balance=EXCLUDED.opening_balance,
               closing_balance=EXCLUDED.closing_balance,opening_paise=EXCLUDED.opening_paise,
               closing_paise=EXCLUDED.closing_paise,active=EXCLUDED.active,
               gstin=EXCLUDED.gstin,tax_type=EXCLUDED.tax_type,
               deactivated_at=CASE WHEN EXCLUDED.active THEN NULL ELSE NOW() END,synced_at=NOW()""",
            device.firm_id, device.client_id, device.installation_id, device.company_name,
            device.company_guid, ledger["guid"], values["name"], values["parent_group"],
            Decimal(values["opening_paise"]) / 100, Decimal(values["closing_paise"]) / 100,
            values["opening_paise"], values["closing_paise"], ledger.get("is_revenue", False),
            values["active"], values["gstin"], values["tax_type"],
        )
        await conn.execute(
            """INSERT INTO connector_mappings(firm_id,client_id,installation_id,mapping_type,
               internal_id,provider_id,normalized_name,source,confidence)
               VALUES($1,$2,$3,'ledger',$4,$5,$4,'EXACT',1)
               ON CONFLICT(installation_id,mapping_type,internal_id) WHERE active DO UPDATE SET
               provider_id=EXCLUDED.provider_id,normalized_name=EXCLUDED.normalized_name""",
            device.firm_id, device.client_id, device.installation_id,
            values["name"], ledger["guid"],
        )
    for voucher in vouchers:
        await _ingest_voucher(conn, device, voucher)
    await _reconcile_window(conn, device, payload, [item["guid"] for item in vouchers])
    return len(ledgers), len(vouchers)


async def _ingest_voucher(conn, device, voucher: dict) -> None:
    entries = [{
        "ledger_name": str(line["ledger_name"]),
        "amount_paise": int(line.get("amount_paise", 0)),
    } for line in voucher.get("entries", [])]
    values = {
        "company_guid": device.company_guid, "remote_id": str(voucher.get("remote_id") or ""),
        "voucher_number": str(voucher.get("voucher_number") or "UNNUMBERED"),
        "date": str(voucher["date"]), "voucher_type": str(voucher["voucher_type"]),
        "party_ledger": str(voucher.get("party_name") or ""),
        "party_gstin": str(voucher.get("party_gstin") or ""),
        "place_of_supply": str(voucher.get("place_of_supply") or ""),
        "narration": str(voucher.get("narration") or ""),
        "reference": str(voucher.get("reference") or ""), "entries": entries,
        "total_paise": voucher_total(entries), "altered": bool(voucher.get("altered")),
        "cancelled": bool(voucher.get("cancelled")),
        "master_id": str(voucher.get("master_id") or ""),
        "alteration_id": str(voucher.get("alteration_id") or ""),
        "provider_status": str(voucher.get("status") or "ACTIVE"),
        "gst_details": list(voucher.get("gst_details") or []),
        "e_invoice": dict(voucher.get("e_invoice") or {}),
        "tax_total_paise": sum(abs(int(item.get("amount_paise", 0)))
                               for item in voucher.get("gst_details") or []),
    }
    object_id, _ = await upsert_snapshot(
        conn, firm_id=device.firm_id, installation_id=device.installation_id,
        object_type="tally_voucher", provider_id=voucher["guid"], values=values,
        status="CANCELLED" if values["cancelled"] else "ACTIVE", void=values["cancelled"],
    )
    await conn.execute(
        """INSERT INTO tally_vouchers(firm_id,client_id,installation_id,company_name,
           company_guid,tally_guid,remote_id,voucher_number,date,voucher_type,party_name,
           narration,reference,entries,snapshot_hash,active,altered,master_id,alteration_id,
           provider_status,gst_details,tax_total_paise,synced_at)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14::jsonb,
           (SELECT snapshot_hash FROM provider_objects WHERE id=$15),$16,$17,$18,$19,$20,$21::jsonb,$22,NOW())
           ON CONFLICT(firm_id,tally_guid) DO UPDATE SET remote_id=EXCLUDED.remote_id,
           voucher_number=EXCLUDED.voucher_number,date=EXCLUDED.date,
           voucher_type=EXCLUDED.voucher_type,party_name=EXCLUDED.party_name,
           narration=EXCLUDED.narration,reference=EXCLUDED.reference,entries=EXCLUDED.entries,
           snapshot_hash=EXCLUDED.snapshot_hash,active=EXCLUDED.active,
           deleted=false,altered=EXCLUDED.altered,master_id=EXCLUDED.master_id,
           alteration_id=EXCLUDED.alteration_id,provider_status=EXCLUDED.provider_status,
           gst_details=EXCLUDED.gst_details,tax_total_paise=EXCLUDED.tax_total_paise,synced_at=NOW()""",
        device.firm_id, device.client_id, device.installation_id, device.company_name,
        device.company_guid, voucher["guid"], values["remote_id"], values["voucher_number"],
        values["date"], values["voucher_type"], values["party_ledger"], values["narration"],
        values["reference"], json.dumps(entries), object_id, not values["cancelled"],
        values["altered"], values["master_id"], values["alteration_id"],
        values["provider_status"], json.dumps(values["gst_details"]), values["tax_total_paise"],
    )
    await _project_register(conn, device, voucher["guid"], values, object_id, snapshot_hash(values))


async def _project_register(conn, device, guid: str, values: dict, object_id: str, version: str) -> None:
    kind = values["voucher_type"].lower()
    if "purchase" not in kind and "sales" not in kind:
        return
    common=(f"tally-{guid}",device.firm_id,device.client_id,period_for(values["date"]),guid,
            values["voucher_number"],values["party_ledger"],values["date"],values["total_paise"],
            values["tax_total_paise"],"Cancelled" if values["cancelled"] else "Synced",object_id,
            f"TALLY_PRIME:{object_id}",version,json.dumps([{"kind":"provider_object","id":object_id}]),not values["cancelled"])
    tax={key:sum(abs(int(item.get("amount_paise",0))) for item in values["gst_details"] if key in str(item.get("tax_type") or "").upper()) for key in ("CGST","SGST","IGST","CESS")}
    if "purchase" in kind:
        await conn.execute(
            """INSERT INTO purchase_register(id,firm_id,client_id,period,tally_voucher_guid,bill_number,
               vendor_name,bill_date,total_paise,tax_total_paise,status,source,provider,provider_object_id,
               source_identity,source_version,evidence,active,taxable_paise,cgst_paise,sgst_paise,igst_paise)
               VALUES($1,$2,$3,$4,$5,$6,$7,to_date($8,'YYYYMMDD'),$9,$10,$11,'TALLY','TALLY_PRIME',$12,$13,$14,$15::jsonb,$16,$17,$18,$19,$20)
               ON CONFLICT(firm_id,client_id,tally_voucher_guid) WHERE tally_voucher_guid IS NOT NULL
               DO UPDATE SET bill_number=EXCLUDED.bill_number,vendor_name=EXCLUDED.vendor_name,
               bill_date=EXCLUDED.bill_date,total_paise=EXCLUDED.total_paise,tax_total_paise=EXCLUDED.tax_total_paise,
               status=EXCLUDED.status,period=EXCLUDED.period,provider_object_id=EXCLUDED.provider_object_id,
               source_version=EXCLUDED.source_version,evidence=EXCLUDED.evidence,active=EXCLUDED.active,
               taxable_paise=EXCLUDED.taxable_paise,cgst_paise=EXCLUDED.cgst_paise,
               sgst_paise=EXCLUDED.sgst_paise,igst_paise=EXCLUDED.igst_paise,synced_at=NOW()""",
            *common,max(0,values["total_paise"]-values["tax_total_paise"]),tax["CGST"],tax["SGST"],tax["IGST"],
        )
        return
    await conn.execute(
        """INSERT INTO sales_register(id,firm_id,client_id,period,tally_voucher_guid,invoice_number,
           customer_name,invoice_date,total_paise,tax_total_paise,status,provider,provider_object_id,
           source_identity,source_version,evidence,active,customer_gstin,place_of_supply,taxable_paise,
           cgst_paise,sgst_paise,igst_paise,cess_paise,e_invoice)
           VALUES($1,$2,$3,$4,$5,$6,$7,to_date($8,'YYYYMMDD'),$9,$10,$11,'TALLY_PRIME',$12,$13,$14,$15::jsonb,$16,
           $17,$18,$19,$20,$21,$22,$23,$24::jsonb)
           ON CONFLICT(firm_id,client_id,tally_voucher_guid) WHERE tally_voucher_guid IS NOT NULL
           DO UPDATE SET invoice_number=EXCLUDED.invoice_number,customer_name=EXCLUDED.customer_name,
           invoice_date=EXCLUDED.invoice_date,total_paise=EXCLUDED.total_paise,
           tax_total_paise=EXCLUDED.tax_total_paise,status=EXCLUDED.status,period=EXCLUDED.period,
           provider_object_id=EXCLUDED.provider_object_id,source_version=EXCLUDED.source_version,evidence=EXCLUDED.evidence,
           active=EXCLUDED.active,customer_gstin=EXCLUDED.customer_gstin,place_of_supply=EXCLUDED.place_of_supply,
           taxable_paise=EXCLUDED.taxable_paise,cgst_paise=EXCLUDED.cgst_paise,sgst_paise=EXCLUDED.sgst_paise,
           igst_paise=EXCLUDED.igst_paise,cess_paise=EXCLUDED.cess_paise,e_invoice=EXCLUDED.e_invoice,synced_at=NOW()""",
        *common,values["party_gstin"],values["place_of_supply"],
        max(0,values["total_paise"]-values["tax_total_paise"]),tax["CGST"],tax["SGST"],tax["IGST"],tax["CESS"],
        json.dumps({key:value for key,value in values["e_invoice"].items() if value}),
    )


async def _reconcile_window(conn, device, payload: dict, seen: list[str]) -> None:
    if payload.get("completeness") != "COMPLETE":
        return
    period = payload["period"]
    await conn.execute(
        """UPDATE tally_vouchers SET deleted=true,active=false WHERE installation_id=$1
           AND date BETWEEN $2 AND $3 AND NOT(tally_guid=ANY($4::text[]))""",
        device.installation_id, period["from_date"], period["to_date"], seen,
    )
    ledger_ids = [item["guid"] for item in payload.get("ledgers", [])]
    await conn.execute(
        """UPDATE tally_ledgers SET active=false,deactivated_at=COALESCE(deactivated_at,NOW())
           WHERE installation_id=$1
           AND NOT(tally_guid=ANY($2::text[]))""", device.installation_id, ledger_ids,
    )
    await conn.execute(
        """UPDATE provider_objects SET deleted=true,active=false,status='DISAPPEARED'
           WHERE installation_id=$1 AND object_type='tally_ledger'
           AND NOT(provider_id=ANY($2::text[]))""", device.installation_id, ledger_ids,
    )
    for table, date_column in (("sales_register", "invoice_date"), ("purchase_register", "bill_date")):
        await conn.execute(
        f"""UPDATE {table} SET status='Deleted',active=false,superseded_at=NOW(),synced_at=NOW() WHERE firm_id=$1
               AND client_id=$2 AND tally_voucher_guid IS NOT NULL
               AND {date_column} BETWEEN to_date($3,'YYYYMMDD') AND to_date($4,'YYYYMMDD')
               AND NOT(tally_voucher_guid=ANY($5::text[]))""",
            device.firm_id, device.client_id, period["from_date"], period["to_date"], seen,
        )
    await conn.execute(
        """UPDATE provider_objects SET deleted=true,active=false,status='DISAPPEARED'
           WHERE installation_id=$1 AND object_type='tally_voucher'
           AND snapshot->>'date' BETWEEN $2 AND $3 AND NOT(provider_id=ANY($4::text[]))""",
        device.installation_id, period["from_date"], period["to_date"], seen,
    )
    await _record_windows(conn,device,payload)


async def _record_windows(conn,device,payload:dict)->None:
    code=period_for(payload["period"]["from_date"])
    for register,word,table in (("SALES","sales","sales_register"),("PURCHASE","purchase","purchase_register")):
        vouchers=[item for item in payload.get("vouchers",[]) if word in str(item.get("voucher_type") or "").lower() and not item.get("cancelled")]
        expected={"taxable":0,"tax":0,"total":0}
        for item in vouchers:
            total=voucher_total(item.get("entries",[]))
            tax=sum(abs(int(x.get("amount_paise",0))) for x in item.get("gst_details",[]))
            expected["total"]+=total;expected["tax"]+=tax;expected["taxable"]+=max(0,total-tax)
        projected=await conn.fetchrow(
            f"""SELECT count(*) count,COALESCE(sum(taxable_paise),0) taxable,
               COALESCE(sum(tax_total_paise),0) tax,COALESCE(sum(total_paise),0) total
               FROM {table} WHERE firm_id=$1 AND client_id=$2 AND period=$3
               AND provider='TALLY_PRIME' AND active""",device.firm_id,device.client_id,code)
        actual={key:int(projected[key]) for key in ("taxable","tax","total")}
        state="COMPLETE" if int(projected["count"])==len(vouchers) and actual==expected else "MISMATCH"
        await conn.execute(
            """INSERT INTO register_sync_windows(firm_id,client_id,provider,register_type,period,state,
               expected_count,processed_count,expected_totals,processed_totals,complete_through)
               VALUES($1,$2,'TALLY_PRIME',$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,
               CASE WHEN $5='COMPLETE' THEN NOW() END)
               ON CONFLICT(firm_id,client_id,provider,register_type,period) DO UPDATE SET
               state=EXCLUDED.state,expected_count=EXCLUDED.expected_count,processed_count=EXCLUDED.processed_count,
               expected_totals=EXCLUDED.expected_totals,processed_totals=EXCLUDED.processed_totals,
               complete_through=EXCLUDED.complete_through,updated_at=NOW()""",
            device.firm_id,device.client_id,register,code,state,len(vouchers),int(projected["count"]),
            json.dumps(expected),json.dumps(actual))
