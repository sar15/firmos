"""Versioned accounting-draft persistence."""
from __future__ import annotations

import json

from core.finance_actions import compute_payload_hash


async def save_draft(db_pool, *, firm_id: str, client_id: str, document_id: str,
                     provider: str, operation: str, status: str, payload: dict,
                     mappings: dict, totals: dict, validation_state: str,
                     missing: list[str], action_id: str | None, changed_by: str,
                     reason: str) -> dict:
    """Upsert the current draft and append its immutable revision in one transaction."""
    digest = compute_payload_hash(payload) if payload else None
    async with db_pool.acquire() as conn:
        draft = await conn.fetchrow(
            """INSERT INTO accounting_drafts(firm_id,client_id,document_id,provider,operation,status,payload,
               missing_mappings,action_id,version,schema_version,validation_state,mappings,totals,payload_hash)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9,1,'purchase.v1',$10,$11::jsonb,$12::jsonb,$13)
               ON CONFLICT(firm_id,document_id,provider,operation) DO UPDATE SET
                 status=EXCLUDED.status,payload=EXCLUDED.payload,missing_mappings=EXCLUDED.missing_mappings,
                 action_id=EXCLUDED.action_id,version=accounting_drafts.version+1,
                 validation_state=EXCLUDED.validation_state,mappings=EXCLUDED.mappings,totals=EXCLUDED.totals,
                 payload_hash=EXCLUDED.payload_hash,updated_at=NOW()
               RETURNING *""", firm_id, client_id, document_id, provider, operation, status,
            json.dumps(payload), json.dumps(missing), action_id, validation_state,
            json.dumps(mappings), json.dumps(totals), digest,
        )
        await conn.execute(
            """INSERT INTO accounting_draft_revisions(draft_id,firm_id,version,schema_version,payload,mappings,
               totals,validation_state,payload_hash,changed_by,change_reason)
               VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8,$9,$10,$11)""",
            draft["id"], firm_id, draft["version"], draft["schema_version"], json.dumps(payload),
            json.dumps(mappings), json.dumps(totals), validation_state, digest, changed_by, reason,
        )
    return dict(draft)
