"""Bank candidate review, posting proposals, and reconciliation proof."""
from __future__ import annotations

from datetime import timedelta
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.deps import FirmContext, get_current_firm, get_db
from core.finance_actions.engine import FinanceActionEngine
from engines.bank_matcher import ALGORITHM_VERSION, BookCandidate, score_candidates
from engines.bank_types import BankTransaction

router = APIRouter(prefix="/api/bank-reconciliation", tags=["bank-reconciliation"])


def _bank_transaction(row) -> BankTransaction:
    return BankTransaction(
        txn_date=row["txn_date"], value_date=row["value_date"], description=row["description"],
        reference=row["reference"] or "", debit_paise=row["debit_paise"], credit_paise=row["credit_paise"],
        balance_paise=row["running_balance"], source_row=row["source_row"], source_page=row["source_page"],
        normalized_tokens=tuple(row["normalized_tokens"]),
    )


async def _book_candidates(conn, firm_id: str, client_id: str, start, end) -> list[BookCandidate]:
    rows = await conn.fetch(
        """SELECT 'INVOICE' source,id candidate_id,invoice_date txn_date,total_paise amount,
                  customer_name party,invoice_number reference FROM sales_register
           WHERE firm_id=$1 AND client_id=$2 AND invoice_date BETWEEN $3 AND $4
           UNION ALL
           SELECT 'PAYMENT',id,bill_date,total_paise,vendor_name,bill_number FROM purchase_register
           WHERE firm_id=$1 AND client_id=$2 AND bill_date BETWEEN $3 AND $4""",
        firm_id, client_id, start - timedelta(days=7), end + timedelta(days=7),
    )
    candidates = [BookCandidate(row["source"], row["candidate_id"], row["txn_date"], int(row["amount"]), row["party"] or "", row["reference"] or "") for row in rows]
    actions = await conn.fetch(
        """SELECT id,operation,payload,created_at::date txn_date FROM finance_actions
           WHERE firm_id=$1 AND client_id=$2 AND created_at::date BETWEEN $3 AND $4""",
        firm_id, client_id, start - timedelta(days=7), end + timedelta(days=7),
    )
    for row in actions:
        payload = row["payload"] or {}
        amount = int(payload.get("amount_paise") or payload.get("total_paise") or 0)
        if amount:
            source = "RECEIPT" if "receipt" in row["operation"].lower() else "VOUCHER"
            candidates.append(BookCandidate(source, str(row["id"]), row["txn_date"], amount,
                                            str(payload.get("party") or ""), str(payload.get("reference") or "")))
    return candidates


@router.post("/{statement_id}/candidates")
async def generate_candidates(statement_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.read")
    async with db_pool.acquire() as conn:
        statement = await conn.fetchrow("SELECT * FROM bank_statements WHERE id=$1 AND firm_id=$2", statement_id, firm.firm_id)
        if not statement:
            raise HTTPException(status_code=404, detail="Bank statement not found")
        rows = await conn.fetch("SELECT * FROM bank_transactions WHERE statement_id=$1 ORDER BY txn_date,id", statement_id)
        candidates = await _book_candidates(conn, firm.firm_id, statement["client_id"], statement["period_start"], statement["period_end"])
        created = 0
        for row in rows:
            transaction = _bank_transaction(row)
            for scored in score_candidates(transaction, candidates):
                await conn.execute(
                    """INSERT INTO bank_match_candidates
                       (firm_id,client_id,statement_id,bank_transaction_id,candidate_source,candidate_id,algorithm_version,score,reasons,candidate_snapshot)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb) ON CONFLICT DO NOTHING""",
                    firm.firm_id, statement["client_id"], statement_id, row["id"], scored.candidate.source,
                    scored.candidate.candidate_id, ALGORITHM_VERSION, scored.score, json.dumps(scored.reasons),
                    json.dumps({"date": scored.candidate.txn_date.isoformat(), "amount_paise": scored.candidate.amount_paise,
                                "party": scored.candidate.party, "reference": scored.candidate.reference}),
                )
                created += 1
    return {"statementId": statement_id, "candidateCount": created, "algorithmVersion": ALGORITHM_VERSION}


@router.get("/{statement_id}")
async def workspace(statement_id: str, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    async with db_pool.acquire() as conn:
        statement = await conn.fetchrow("SELECT * FROM bank_statements WHERE id=$1 AND firm_id=$2", statement_id, firm.firm_id)
        if not statement:
            raise HTTPException(status_code=404, detail="Bank statement not found")
        rows = await conn.fetch(
            """SELECT c.*,t.txn_date,t.description,t.reference,t.debit_paise,t.credit_paise,t.running_balance
               FROM bank_match_candidates c JOIN bank_transactions t ON t.id=c.bank_transaction_id
               WHERE c.statement_id=$1 ORDER BY t.txn_date,c.score DESC""", statement_id,
        )
    return {"statement": dict(statement), "candidates": [dict(row) for row in rows]}


class CandidateDecision(BaseModel):
    decision: str


@router.patch("/candidates/{candidate_id}")
async def decide_candidate(candidate_id: uuid.UUID, body: CandidateDecision, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.approve")
    status = body.decision.upper()
    if status not in {"ACCEPTED", "REJECTED"}:
        raise HTTPException(status_code=422, detail="Decision must be accepted or rejected")
    async with db_pool.acquire() as conn:
        candidate = await conn.fetchrow("SELECT * FROM bank_match_candidates WHERE id=$1 AND firm_id=$2", candidate_id, firm.firm_id)
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if status == "ACCEPTED":
            await conn.execute("UPDATE bank_match_candidates SET status='REJECTED',decided_by=$1::uuid,decided_at=NOW() WHERE bank_transaction_id=$2 AND id<>$3", firm.user_id, candidate["bank_transaction_id"], candidate_id)
        await conn.execute("UPDATE bank_match_candidates SET status=$1,decided_by=$2::uuid,decided_at=NOW() WHERE id=$3", status, firm.user_id, candidate_id)
    return {"ok": True, "status": status}


class PostingProposal(BaseModel):
    candidate_id: uuid.UUID
    action_type: str
    provider: str


@router.post("/posting-proposals")
async def propose_posting(body: PostingProposal, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.propose")
    action_type = body.action_type.upper()
    if action_type not in {"RECEIPT", "PAYMENT", "CONTRA", "JOURNAL"}:
        raise HTTPException(status_code=422, detail="Choose receipt, payment, contra, or journal")
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT c.*,t.description,t.reference,t.debit_paise,t.credit_paise FROM bank_match_candidates c
               JOIN bank_transactions t ON t.id=c.bank_transaction_id WHERE c.id=$1 AND c.firm_id=$2 AND c.status='ACCEPTED'""",
            body.candidate_id, firm.firm_id,
        )
    if not row:
        raise HTTPException(status_code=409, detail="Accept a candidate before preparing a posting proposal")
    payload = {"action_type": action_type, "bank_transaction_id": row["bank_transaction_id"],
               "candidate_id": row["candidate_id"], "description": row["description"],
               "reference": row["reference"], "amount_paise": row["credit_paise"] or row["debit_paise"]}
    action = await FinanceActionEngine(db_pool).propose_action(
        firm.firm_id, row["client_id"], body.provider, f"bank.write.{action_type.lower()}.create", payload,
        f"bank:{row['bank_transaction_id']}:{action_type}", proposed_by=firm.user_id, risk_level="MEDIUM",
        source_identity=row["bank_transaction_id"],
    )
    return {"actionId": str(action["id"]), "status": action["status"], "approvalRequired": True, "executed": False}


class ProofRequest(BaseModel):
    explanation: str | None = None
    complete: bool = False


@router.post("/{statement_id}/proofs")
async def create_proof(statement_id: str, body: ProofRequest, firm: FirmContext = Depends(get_current_firm), db_pool=Depends(get_db)):
    firm.require("books.approve")
    async with db_pool.acquire() as conn:
        statement = await conn.fetchrow("SELECT * FROM bank_statements WHERE id=$1 AND firm_id=$2", statement_id, firm.firm_id)
        if not statement:
            raise HTTPException(status_code=404, detail="Bank statement not found")
        totals = await conn.fetchrow(
            """SELECT COALESCE(SUM(t.amount),0) total,
                      COALESCE(SUM(t.amount) FILTER (WHERE c.status='ACCEPTED'),0) matched
               FROM bank_transactions t LEFT JOIN bank_match_candidates c ON c.bank_transaction_id=t.id
                 AND c.status='ACCEPTED' WHERE t.statement_id=$1""", statement_id,
        )
        unmatched = int(totals["total"] - totals["matched"])
        if body.complete and unmatched:
            raise HTTPException(status_code=409, detail={"code": "UNEXPLAINED_BALANCE", "difference_paise": unmatched})
        version = await conn.fetchval("SELECT COALESCE(MAX(version),0)+1 FROM bank_reconciliation_proofs WHERE statement_id=$1", statement_id)
        proof_id = await conn.fetchval(
            """INSERT INTO bank_reconciliation_proofs
               (firm_id,client_id,statement_id,version,statement_balance_paise,matched_paise,unmatched_paise,
                unresolved_difference_paise,explanation,completed,reviewer_id)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$7,$8,$9,$10::uuid) RETURNING id""",
            firm.firm_id, statement["client_id"], statement_id, version,
            int(statement["closing_balance_paise"] or 0), int(totals["matched"]), unmatched,
            body.explanation, body.complete, firm.user_id,
        )
    return {"proofId": str(proof_id), "version": version, "matched_paise": int(totals["matched"]),
            "unmatched_paise": unmatched, "completed": body.complete}
