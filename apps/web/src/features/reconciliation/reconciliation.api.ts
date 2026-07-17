import { ReconMode, ReconMatch } from "@/types";
import { getAuthHeaders } from "@/lib/auth";

export interface ReconciliationResponse {
  matches: ReconMatch[];
  summary: {
    autoMatched: number;
    suggested: number;
    unmatched: number;
    totalAutoMatched: number;
    totalSuggested: number;
    totalUnmatched: number;
  };
}

export interface EvidenceUploadResult {
  runId?: string;
  statementId?: string;
  status?: string;
  identityErrors?: Array<{ code: string; selected: string; file: string }>;
  duplicateUpload?: boolean;
  balanceValidation?: { valid: boolean; reason?: string; breaks?: unknown[] };
}

async function responseJson<T>(res: Response): Promise<T> {
  const payload = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message || `Request failed (${res.status})`);
  }
  return payload;
}

export async function uploadEvidence(file: File, clientId: string, period: string, mode: ReconMode): Promise<EvidenceUploadResult> {
  const form = new FormData();
  form.append("file", file);
  form.append("client_id", clientId);
  if (mode === "GSTR2B_VS_PURCHASE") form.append("period", period);
  const path = mode === "GSTR2B_VS_PURCHASE" ? "/api/gstr2b/runs" : "/api/bank-statements/upload";
  const auth = await getAuthHeaders();
  return responseJson(await fetch(path, { method: "POST", headers: { Authorization: auth.Authorization || "" }, body: form }));
}

export async function previewGstr2bBulk(runId: string, confirm = false): Promise<{ count: number; total_paise: number }> {
  const res = await fetch(`/api/gstr2b/runs/${runId}/bulk-accept?confirm=${confirm}`, { method: "POST", headers: await getAuthHeaders() });
  return responseJson(res);
}

export async function createGstr2bWorkpaper(runId: string): Promise<{ version: number }> {
  const res = await fetch(`/api/gstr2b/runs/${runId}/workpapers`, { method: "POST", headers: await getAuthHeaders() });
  return responseJson(res);
}

export async function prepareBankCandidates(statementId: string): Promise<{ candidateCount: number }> {
  const res = await fetch(`/api/bank-reconciliation/${statementId}/candidates`, { method: "POST", headers: await getAuthHeaders() });
  return responseJson(res);
}

export async function getGstr2bWorkspace(runId: string): Promise<ReconMatch[]> {
  const res = await fetch(`/api/gstr2b/runs/${runId}`, { headers: await getAuthHeaders() });
  const data = await responseJson<{ items: Array<Record<string, unknown>> }>(res);
  return data.items.map((item) => {
    const bucket = String(item.bucket);
    const book = item.purchase_id ? {
      id: String(item.purchase_id || `missing-book-${item.id}`), date: String(item.bill_date || item.invoice_date || ""),
      description: String(item.vendor_name || "Purchase missing in books"), counterparty: String(item.vendor_name || item.supplier_gstin || "Unknown"),
      amount: Number(item.book_total_paise || item.total_paise || 0), ref: String(item.bill_number || item.invoice_number || ""),
      gstin: String(item.vendor_gstin || item.supplier_gstin || ""),
    } : null;
    const portal = item.gstr2b_document_id ? {
      id: String(item.gstr2b_document_id), date: String(item.invoice_date || ""), description: String(item.document_type || "GSTR-2B document"),
      counterparty: String(item.supplier_gstin || "Unknown supplier"), amount: Number(item.total_paise || 0),
      ref: String(item.invoice_number || ""), gstin: String(item.supplier_gstin || ""),
    } : undefined;
    const status = bucket === "EXACT" ? "AUTO_MATCHED" : ["PROBABLE", "MISMATCH", "MANUAL_REVIEW", "AMENDMENT_CREDIT_NOTE"].includes(bucket) ? "SUGGESTED" : "UNMATCHED";
    return { id: String(item.id), status, score: item.score == null ? undefined : Number(item.score), source: book, target: portal,
      reasons: Array.isArray(item.reasons) ? item.reasons.map(String) : [],
      flag: bucket === "MISMATCH" ? "AMOUNT_MISMATCH" : undefined } as ReconMatch;
  });
}

export async function getBankWorkspace(statementId: string): Promise<ReconMatch[]> {
  const res = await fetch(`/api/bank-reconciliation/${statementId}`, { headers: await getAuthHeaders() });
  const data = await responseJson<{ candidates: Array<Record<string, unknown>> }>(res);
  return data.candidates.filter((item) => item.status !== "REJECTED").map((item) => {
    const snapshot = (item.candidate_snapshot || {}) as Record<string, unknown>;
    const credit = Number(item.credit_paise || 0);
    return {
      id: String(item.id), status: item.status === "ACCEPTED" ? "AUTO_MATCHED" : "SUGGESTED", score: Number(item.score),
      source: { id: String(item.bank_transaction_id), date: String(item.txn_date), description: String(item.description),
        counterparty: "Bank statement", amount: credit || -Number(item.debit_paise || 0), ref: String(item.reference || "") },
      target: { id: String(item.candidate_id), date: String(snapshot.date || ""), description: String(item.candidate_source),
        counterparty: String(snapshot.party || "Books"), amount: Number(snapshot.amount_paise || 0), ref: String(snapshot.reference || "") },
      reasons: Array.isArray(item.reasons) ? item.reasons.map(String) : [],
    } as ReconMatch;
  });
}

export async function decideGstr2bMatch(matchId: string, accepted: boolean): Promise<void> {
  const res = await fetch(`/api/gstr2b/matches/${matchId}`, { method: "PATCH", headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ match_decision: accepted ? "ACCEPTED" : "REJECTED", ims_decision: "NO_ACTION" }) });
  await responseJson(res);
}

export async function decideBankCandidate(candidateId: string, accepted: boolean): Promise<void> {
  const res = await fetch(`/api/bank-reconciliation/candidates/${candidateId}`, { method: "PATCH", headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ decision: accepted ? "ACCEPTED" : "REJECTED" }) });
  await responseJson(res);
}

export async function createBankProof(statementId: string): Promise<{ version: number; unmatched_paise: number }> {
  const res = await fetch(`/api/bank-reconciliation/${statementId}/proofs`, { method: "POST", headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ complete: false }) });
  return responseJson(res);
}

export async function getReconciliation(clientId: string, mode: ReconMode, period: string): Promise<ReconciliationResponse> {
  const res = await fetch(`/api/reconciliation/${clientId}?mode=${mode}&period=${encodeURIComponent(period)}`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to get reconciliation: ${res.statusText}`);
  return res.json();
}

export async function acceptMatch(match: ReconMatch, clientId: string, mode: ReconMode, period: string): Promise<{ ok: boolean }> {
  if (!match.source) throw new Error("A portal-only entry cannot be accepted as a books match.");
  const res = await fetch(`/api/reconciliation/matches/${match.id}/accept`, {
    method: "POST",
    headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, period, mode, source_id: match.source.id, target_id: match.target?.id }),
  });
  if (!res.ok) throw new Error(`Failed to accept match: ${res.statusText}`);
  return res.json();
}

export async function rejectMatch(match: ReconMatch, clientId: string, mode: ReconMode, period: string): Promise<{ ok: boolean }> {
  if (!match.source) throw new Error("A portal-only entry cannot be rejected as a books match.");
  const res = await fetch(`/api/reconciliation/matches/${match.id}/reject`, {
    method: "POST",
    headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ client_id: clientId, period, mode, source_id: match.source.id, target_id: match.target?.id }),
  });
  if (!res.ok) throw new Error(`Failed to reject match: ${res.statusText}`);
  return res.json();
}

export async function bulkAcceptClean(clientId: string, mode: ReconMode, period: string): Promise<{ ok: boolean }> {
  const res = await fetch(`/api/reconciliation/bulk-accept?mode=${mode}&client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to bulk accept: ${res.statusText}`);
  return res.json();
}

export async function upload2BJson(clientId: string, period: string, payload: Record<string, unknown>): Promise<ReconciliationResponse> {
  const res = await fetch(`/api/reconciliation/upload-2b?client_id=${encodeURIComponent(clientId)}&period=${encodeURIComponent(period)}`, {
    method: "POST",
    headers: {
      ...await getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Failed to upload GSTR-2B JSON: ${res.statusText}`);
  return res.json();
}
