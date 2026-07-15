import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from api.deps import get_current_firm, FirmContext, get_db
from models.schemas import Decision
from api.routes.decision_format import as_decision, enrich_context_with_math

router = APIRouter(prefix="/api/decisions", tags=["decisions"])

@router.get("", response_model=list[Decision])
async def list_decisions(
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """GET /api/decisions"""
    if not db_pool:
        raise HTTPException(status_code=503, detail="Database connection required")
        
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM decisions WHERE firm_id = $1 ORDER BY created_at DESC",
                firm.firm_id
            )
            return [as_decision(row) for row in rows]
    except Exception:
        raise

@router.get("/{decision_id}", response_model=Decision)
async def get_decision(
    decision_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """GET /api/decisions/{decision_id}"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM decisions WHERE id = $1 AND firm_id = $2",
            decision_id, firm.firm_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
            
        return as_decision(row)

@router.get("/{decision_id}/context")
async def get_decision_context(
    decision_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """GET /api/decisions/{decision_id}/context
    
    Pulls related documents, computation results, and 2B recon results.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT context_data, evidence, draft_response FROM decisions WHERE id = $1 AND firm_id = $2",
            decision_id, firm.firm_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
            
        import json
        context_data = json.loads(row["context_data"]) if row["context_data"] else {}
        evidence = json.loads(row["evidence"]) if row["evidence"] else []

        # Item #5: Wire TDS/interest compute into context when relevant
        decision_row = await conn.fetchrow(
            "SELECT flag, amount FROM decisions WHERE id = $1 AND firm_id = $2",
            decision_id, firm.firm_id,
        )
        if decision_row:
            flag = (decision_row.get("flag") or "").lower()
            amount_paise = decision_row.get("amount", 0) or 0
            enrich_context_with_math(flag, amount_paise, context_data, evidence)

        return {
            "contextData": context_data,
            "evidence": evidence,
            "draftResponse": row["draft_response"]
        }


from typing import Optional

class DraftRequest(BaseModel):
    instructions: Optional[str] = None

class ApproveRequest(BaseModel):
    reviewed_response: str = Field(min_length=1, max_length=20_000)

@router.post("/{decision_id}/draft")
async def draft_decision_response(
    decision_id: str,
    req: DraftRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """POST /api/decisions/{decision_id}/draft
    
    Generates AI-drafted response constrained to engine + notice + ledger facts.
    """
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT context_data, evidence, flag, amount FROM decisions WHERE id = $1 AND firm_id = $2",
            decision_id, firm.firm_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
            
        import json
        import httpx
        from core.config import settings
        
        context_data = json.loads(row["context_data"]) if row["context_data"] else {}
        evidence = json.loads(row["evidence"]) if row["evidence"] else []
        
        flag = (row.get("flag") or "").lower()
        amount_paise = row.get("amount", 0) or 0
        enrich_context_with_math(flag, amount_paise, context_data, evidence)
        
        prompt = f"""You are firmOS, an AI for Chartered Accountants in India.
Draft a professional response or decision memo based ONLY on the following facts.
Do not invent any numbers, dates, or legal claims that are not in the evidence.

Context:
{json.dumps(context_data, indent=2)}

Evidence (from computation engines and source documents):
{json.dumps(evidence, indent=2)}

User Instructions:
{req.instructions or 'Provide a clear recommendation.'}
"""

        draft = ""
        if settings.sarvam_api_key:
            try:
                async with httpx.AsyncClient(timeout=60.0) as http:
                    resp = await http.post(
                        "https://api.sarvam.ai/v1/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "API-Subscription-Key": settings.sarvam_api_key,
                        },
                        json={
                            "model": "sarvam-30b",
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": 0.1,
                            "max_tokens": 512,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    draft = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            except Exception as e:
                import logging
                logging.error(f"Failed to call Sarvam AI for drafting: {e}")
                draft = "Failed to generate draft due to API error."
        else:
            draft = f"Based on the firmOS computation engine and evidence {evidence}, it is observed that {context_data.get('issue', 'there is a mismatch')}."
            
        if not draft or draft == "Failed to generate draft due to API error.":
            draft = f"Based on the firmOS computation engine and evidence {evidence}, it is observed that {context_data.get('issue', 'there is a mismatch')}."
        
        await conn.execute(
            "UPDATE decisions SET draft_response = $1 WHERE id = $2 AND firm_id = $3",
            draft, decision_id, firm.firm_id
        )
        
        return {"draftResponse": draft}


@router.post("/{decision_id}/approve", response_model=Decision)
async def approve_decision(
    decision_id: str,
    req: ApproveRequest,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """POST /api/decisions/{decision_id}/approve"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    async with db_pool.acquire() as conn:
        current = await conn.fetchrow(
            "SELECT * FROM decisions WHERE id = $1 AND firm_id = $2 FOR UPDATE",
            decision_id, firm.firm_id
        )
        if not current:
            raise HTTPException(status_code=404, detail="Decision not found")

        import json
        reviewed_response = req.reviewed_response.strip()
        await conn.execute(
            """INSERT INTO decision_review_versions (
                id, decision_id, firm_id, reviewed_response, reviewed_by
            ) VALUES ($1, $2, $3, $4, $5)""",
            f"drv-{uuid.uuid4().hex[:12]}", decision_id, firm.firm_id, reviewed_response, firm.user_id,
        )
        row = await conn.fetchrow(
            "UPDATE decisions SET status = 'approved' WHERE id = $1 AND firm_id = $2 RETURNING *",
            decision_id, firm.firm_id,
        )
        await conn.execute(
            """
            INSERT INTO audit_log (firm_id, action, actor, details)
            VALUES ($1, $2, $3, $4)
            """,
            firm.firm_id, "HUMAN_APPROVED", "HUMAN",
            json.dumps({"decision_id": decision_id, "flag": row.get("flag", "")})
        )
        
        return as_decision(row, confidence=0.0, recommendation="Human review required for workflow continuation.")


@router.post("/{decision_id}/reject", response_model=Decision)
async def reject_decision(
    decision_id: str,
    firm: FirmContext = Depends(get_current_firm),
    db_pool = Depends(get_db)
):
    """POST /api/decisions/{decision_id}/reject"""
    if not db_pool:
        raise HTTPException(status_code=500, detail="Database not connected")
        
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "UPDATE decisions SET status = 'rejected' WHERE id = $1 AND firm_id = $2 RETURNING *",
            decision_id, firm.firm_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Decision not found")
            
        import json
        await conn.execute(
            """
            INSERT INTO audit_log (firm_id, action, actor, details)
            VALUES ($1, $2, $3, $4)
            """,
            firm.firm_id, "STEP_COMPLETED", "HUMAN",
            json.dumps({"decision_id": decision_id, "action": "rejected"})
        )
            
        return as_decision(row, confidence=0.0, recommendation="Human review required for workflow continuation.")
