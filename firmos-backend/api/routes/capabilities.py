"""Read-only server capability status."""
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from api.deps import FirmContext, get_current_firm, get_db
from connectors.platform.capabilities import CapabilityContext, evaluate_capabilities
from connectors.zoho_books.connector import capabilities_for_scopes

router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])

_PROVIDERS = {"c1": "ZOHO_BOOKS", "c5": "TALLY_PRIME"}


async def _context(firm: FirmContext, db_pool) -> CapabilityContext:
    if not db_pool:
        raise HTTPException(status_code=503, detail={"code": "CAPABILITY_DATABASE_UNAVAILABLE"})
    try:
        async with db_pool.acquire() as conn:
            installations = await conn.fetch(
                """SELECT i.provider,i.status,c.scopes,
                   (i.status='AVAILABLE' AND i.last_probe_at>NOW()-interval '15 minutes'
                    AND (i.provider='TALLY_PRIME' OR EXISTS(
                      SELECT 1 FROM connector_credentials c WHERE c.installation_id=i.id
                      AND c.revoked_at IS NULL
                    ))) AS healthy
                   FROM connector_installations i LEFT JOIN connector_credentials c
                   ON c.installation_id=i.id AND c.revoked_at IS NULL
                   WHERE i.firm_id=$1""", firm.firm_id,
            )
            certifications = await conn.fetch(
                """SELECT c.capability_key,max(c.certification_level) AS level,
                   max(c.provider_version) AS provider_version
                   FROM capability_certifications c JOIN connector_installations i
                   ON i.id=c.installation_id AND i.firm_id=c.firm_id
                   WHERE c.firm_id=$1 AND i.status='AVAILABLE' AND (
                     (c.provider='ZOHO_BOOKS' AND c.provider_version='v3' AND EXISTS(
                       SELECT 1 FROM connector_credentials x WHERE x.installation_id=i.id
                       AND x.revoked_at IS NULL)) OR
                     (c.provider='TALLY_PRIME' AND EXISTS(
                       SELECT 1 FROM tally_devices d WHERE d.installation_id=i.id
                       AND d.status='ACTIVE' AND d.tally_version=c.provider_version))
                   ) GROUP BY c.capability_key""",
                firm.firm_id,
            )
            overrides = await conn.fetch(
                """SELECT firm_id, client_id, installation_id, provider, capability_key, is_enabled
                   FROM capability_overrides WHERE firm_id IS NULL OR firm_id=$1""", firm.firm_id,
            )
            mapping_rows = await conn.fetch(
                """SELECT i.provider,array_agg(DISTINCT m.mapping_type) AS types
                   FROM connector_installations i LEFT JOIN connector_mappings m ON m.installation_id=i.id AND m.active
                   WHERE i.firm_id=$1 GROUP BY i.provider""", firm.firm_id,
            )
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"code": "CAPABILITY_DATABASE_UNAVAILABLE"}) from exc
    return CapabilityContext(
        role=firm.role,
        firm_id=firm.firm_id,
        installations=frozenset(row["provider"] for row in installations),
        healthy_installations=frozenset(row["provider"] for row in installations if row["healthy"]),
        reported_capabilities=frozenset(
            key for row in installations for key in (
                ({"zoho.connection.oauth"} | capabilities_for_scopes(row["scopes"]))
                if row["provider"] == "ZOHO_BOOKS" else {
                    "tally.device.pair", "tally.read.companies", "tally.read.ledgers",
                    "tally.read.vouchers", "tally.write.purchase_voucher.create",
                    "tally.verify.purchase_voucher", "tally.write.sales_voucher.create",
                    "tally.verify.sales_voucher",
                }
            )
        ),
        mapped_capabilities=frozenset(
            key for row in mapping_rows if (
                {"contact", "ledger", "tax"} if row["provider"] == "ZOHO_BOOKS" else {"company", "ledger"}
            ).issubset(set(row["types"] or []))
            for key in (("zoho.write.purchase_bill.create","zoho.write.sales_invoice.create") if row["provider"] == "ZOHO_BOOKS" else
                        ("tally.write.purchase_voucher.create","tally.write.sales_voucher.create"))
        ),
        certification_levels={row["capability_key"]: int(row["level"]) for row in certifications},
        certification_versions={row["capability_key"]: row["provider_version"] for row in certifications},
        overrides=tuple(dict(row) for row in overrides),
    )


@router.get("")
async def list_capabilities(firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    """Return evaluated capability state; this API intentionally has no enable mutation."""
    return {"capabilities": [asdict(item) for item in evaluate_capabilities(await _context(firm, db_pool))]}


@router.get("/{capability_key}")
async def get_capability(capability_key: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    for item in evaluate_capabilities(await _context(firm, db_pool)):
        if item.capability_key == capability_key:
            return asdict(item)
    raise HTTPException(status_code=404, detail={"code": "CAPABILITY_NOT_FOUND"})
