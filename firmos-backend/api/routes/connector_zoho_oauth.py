"""Zoho OAuth install, organization mapping, and reconnect boundary."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from api.deps import FirmContext, get_current_firm, get_db
from connectors.zoho_books.auth import exchange_code_for_tokens, get_authorize_url
from connectors.zoho_books.client import get_organizations
from connectors.zoho_books.connector import CAPABILITIES, capabilities_for_scopes
from connectors.zoho_books.credentials import save_installation_credentials
from core.config import settings
from core.security import decrypt_token, encrypt_token

router = APIRouter()


class OrganizationChoice(BaseModel):
    organization_id: str
    client_id: str


def resolve_zoho_redirect_uri(_request: Request | None = None) -> str:
    """Only the callback configured by the server is trusted."""
    uri = settings.zoho_redirect_uri.strip()
    if not uri:
        raise HTTPException(status_code=503, detail="Zoho callback URL is not configured")
    if not uri.startswith("https://") and settings.firmos_environment not in {"local", "test"}:
        raise HTTPException(status_code=503, detail="Zoho callback URL must use HTTPS")
    return uri


def oauth_state_digest(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def organization_choices(value: object) -> list[dict]:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        raise HTTPException(status_code=500, detail={"code": "CORRUPT_CONNECTOR_STATE"})
    return value


async def start_zoho_oauth(request: Request, firm: FirmContext, db_pool) -> dict:
    redirect_uri = resolve_zoho_redirect_uri(request)
    state = secrets.token_urlsafe(32)
    async with db_pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO oauth_connection_attempts
               (firm_id,user_id,provider,state_digest,redirect_uri,expires_at)
               VALUES($1,$2,'ZOHO_BOOKS',$3,$4,$5)""",
            firm.firm_id, firm.user_id, oauth_state_digest(state), redirect_uri,
            datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    return {"redirect_url": get_authorize_url(state, redirect_uri=redirect_uri)}


@router.get("/callback/zoho")
async def zoho_callback(
    request: Request, code: str, state: str, location: str | None = None,
    db_pool=Depends(get_db),
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    digest = oauth_state_digest(state)
    async with db_pool.acquire() as conn:
        attempt = await conn.fetchrow(
            """SELECT id,state_digest,redirect_uri FROM oauth_connection_attempts
               WHERE state_digest=$1 AND provider='ZOHO_BOOKS' AND status='PENDING_AUTH'
               AND expires_at>NOW()""", digest,
        )
    if not attempt or not secrets.compare_digest(digest, attempt["state_digest"]):
        raise HTTPException(status_code=400, detail="This Zoho connection request has expired or was already used")
    try:
        tokens = await exchange_code_for_tokens(code, attempt["redirect_uri"], location)
        if not tokens.get("refresh_token"):
            raise ValueError("offline access missing")
        orgs = await get_organizations(tokens["access_token"], tokens["api_domain"])
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Zoho authorization could not be completed") from exc
    organizations = [{
        "organization_id": str(org["organization_id"]),
        "name": str(org.get("name") or org.get("organization_name") or "Zoho Books organization"),
        "gstin": str(org.get("gst_no") or org.get("gstin") or ""),
    } for org in orgs if org.get("organization_id")]
    if not organizations:
        raise HTTPException(status_code=400, detail="No Zoho Books organizations were returned")
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(tokens["expires_in"]))
    async with db_pool.acquire() as conn:
        saved = await conn.fetchrow(
            """UPDATE oauth_connection_attempts SET access_token_enc=$2,refresh_token_enc=$3,
               organizations=$4::jsonb,status='AWAITING_ORGANIZATION',data_center=$5,
               api_domain=$6,granted_scopes=$7::text[],token_expires_at=$8,
               updated_at=NOW(),expires_at=NOW()+interval '30 minutes'
               WHERE id=$1 AND status='PENDING_AUTH' AND expires_at>NOW() RETURNING id""",
            attempt["id"], encrypt_token(tokens["access_token"]), encrypt_token(tokens["refresh_token"]),
            json.dumps(organizations), tokens["data_center"], tokens["api_domain"], tokens["scopes"], expires_at,
        )
    if not saved:
        raise HTTPException(status_code=400, detail="This Zoho connection request was already used")
    return RedirectResponse(f"{settings.frontend_url.rstrip('/')}/connectors?zoho_attempt={attempt['id']}")


@router.get("/c1/organization-choice/{attempt_id}")
async def get_zoho_organization_choice(
    attempt_id: str, firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db),
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn:
        attempt = await conn.fetchrow(
            """SELECT id,organizations FROM oauth_connection_attempts WHERE id=$1::uuid
               AND firm_id=$2 AND user_id=$3 AND provider='ZOHO_BOOKS'
               AND status='AWAITING_ORGANIZATION' AND expires_at>NOW()""",
            attempt_id, firm.firm_id, firm.user_id,
        )
    if not attempt:
        raise HTTPException(status_code=404, detail="Zoho organization choice is unavailable")
    return {"attempt_id": str(attempt["id"]), "organizations": organization_choices(attempt["organizations"])}


@router.post("/c1/organization-choice/{attempt_id}")
async def select_zoho_organization(
    attempt_id: str, choice: OrganizationChoice,
    firm: FirmContext=Depends(get_current_firm), db_pool=Depends(get_db),
):
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database not connected")
    async with db_pool.acquire() as conn, conn.transaction():
        attempt = await conn.fetchrow(
            """SELECT * FROM oauth_connection_attempts WHERE id=$1::uuid AND firm_id=$2
               AND user_id=$3 AND provider='ZOHO_BOOKS' AND status='AWAITING_ORGANIZATION'
               AND expires_at>NOW() FOR UPDATE""", attempt_id, firm.firm_id, firm.user_id,
        )
        client = await conn.fetchrow(
            "SELECT id,legal_name,gstin FROM clients WHERE id=$1 AND firm_id=$2",
            choice.client_id, firm.firm_id,
        )
        if not attempt or not client:
            raise HTTPException(status_code=404, detail="Zoho organization or FirmOS client is unavailable")
        organization = next((item for item in organization_choices(attempt["organizations"]) if item["organization_id"] == choice.organization_id), None)
        if not organization:
            raise HTTPException(status_code=400, detail="Select an organization returned by Zoho")
        installation_id = str(attempt["intended_installation_id"])
        warning = None
        if organization.get("gstin") and client["gstin"] and organization["gstin"].upper() != client["gstin"].upper():
            warning = "GSTIN_MISMATCH"
        configuration = {"organization_id": choice.organization_id, "organization_name": organization["name"], "gstin_warning": warning}
        installation = await conn.fetchrow(
            """INSERT INTO connector_installations(id,firm_id,client_id,provider,environment,
               display_name,status,implementation_version,configuration,created_by)
               VALUES($1::uuid,$2,$3,'ZOHO_BOOKS','production',$4,'AVAILABLE','v1',$5::jsonb,$6::uuid)
               ON CONFLICT(firm_id,client_id,provider,environment) DO UPDATE SET status='AVAILABLE',
               display_name=EXCLUDED.display_name,configuration=EXCLUDED.configuration,
               implementation_version='v1',updated_at=NOW() RETURNING id""",
            installation_id, firm.firm_id, choice.client_id, organization["name"], json.dumps(configuration), firm.user_id,
        )
        installation_id = str(installation["id"])
        values = {"access_token": decrypt_token(attempt["access_token_enc"]), "refresh_token": decrypt_token(attempt["refresh_token_enc"])}
        await save_installation_credentials(
            conn, installation_id=installation_id, firm_id=firm.firm_id, values=values,
            data_center=attempt["data_center"], api_domain=attempt["api_domain"],
            scopes=list(attempt["granted_scopes"]), expires_at=attempt["token_expires_at"],
        )
        granted_capabilities = capabilities_for_scopes(attempt["granted_scopes"])
        await conn.executemany(
            """INSERT INTO connector_capabilities
               (installation_id,capability_key,state,reason_code)
               VALUES($1::uuid,$2,$3,$4)
               ON CONFLICT(installation_id,capability_key) DO UPDATE SET
               state=EXCLUDED.state,reason_code=EXCLUDED.reason_code""",
            [
                (installation_id, key, "AVAILABLE" if key in granted_capabilities else "BLOCKED_AUTH",
                 None if key in granted_capabilities else "MISSING_OAUTH_SCOPE")
                for key in sorted(CAPABILITIES)
            ] + [(installation_id, "zoho.connection.oauth", "AVAILABLE", None)],
        )
        await conn.execute(
            """INSERT INTO connector_mappings(firm_id,client_id,installation_id,mapping_type,
               internal_id,provider_id,normalized_name,tax_identity,source,confidence,approved_by,approved_at)
               VALUES($1,$2,$3::uuid,'organization',$2,$4,$5,$6,'MANUAL',1,$7::uuid,NOW())
               ON CONFLICT DO NOTHING""",
            firm.firm_id, choice.client_id, installation_id, choice.organization_id,
            organization["name"], organization.get("gstin") or None, firm.user_id,
        )
        for capability_key in (
            "zoho.sync.contacts", "zoho.sync.accounts", "zoho.sync.items", "zoho.sync.taxes",
        ):
            await conn.execute(
                """INSERT INTO connector_sync_jobs(firm_id,client_id,installation_id,
                   capability_key,status,correlation_id)
                   VALUES($1,$2,$3::uuid,$4,'QUEUED',$5)""",
                firm.firm_id, choice.client_id, installation_id, capability_key, attempt_id,
            )
        await conn.execute(
            """UPDATE oauth_connection_attempts SET status='CONSUMED',completed_at=NOW(),
               access_token_enc=NULL,refresh_token_enc=NULL,organizations='[]',updated_at=NOW()
               WHERE id=$1::uuid""", attempt_id,
        )
    return {"status": "CONNECTED", "installation_id": installation_id, "organization_name": organization["name"], "warning": warning}
