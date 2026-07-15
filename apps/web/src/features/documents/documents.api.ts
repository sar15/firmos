import { ExtractedDocument } from "@/types";
import { getAuthHeaders } from "@/lib/auth";

export async function listDocuments(): Promise<ExtractedDocument[]> {
  const res = await fetch(`/api/documents`, { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to list documents: ${res.statusText}`);
  return res.json();
}

export async function getDocument(id: string): Promise<ExtractedDocument | null> {
  const res = await fetch(`/api/documents/${id}`, { headers: await getAuthHeaders() });
  if (!res.ok) {
    if (res.status === 404) return null;
    throw new Error(`Failed to get document: ${res.statusText}`);
  }
  return res.json();
}

export async function resolveDocumentEvidence(fileUrl: string): Promise<string> {
  if (!fileUrl.startsWith("/api/documents/")) return fileUrl;
  const res = await fetch(fileUrl, { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error("Could not open private document evidence");
  return (await res.json()).url as string;
}

export async function updateField(
  id: string,
  key: string,
  value: string
): Promise<ExtractedDocument> {
  const res = await fetch(`/api/documents/${id}/fields/${key}?value=${encodeURIComponent(value)}`, {
    method: "PUT",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to update field: ${res.statusText}`);
  return res.json();
}

export type DocumentActionProposal = {
  provider: "ZOHO_BOOKS" | "TALLY_PRIME";
  status: "NEEDS_MAPPING" | "ACTION_PROPOSED";
  missing_mappings: string[];
  vendor_candidates: { id: string; label: string }[];
  account_candidates: { id: string; label: string }[];
  customer_candidates: { id: string; label: string }[];
  item_candidates: { id: string; label: string }[];
  tax_candidates: { id: string; label: string }[];
  action_id?: string;
  payload_hash?: string;
};

export type DocumentMapping = {
  provider?: "ZOHO_BOOKS" | "TALLY_PRIME";
  vendor_id?: string; account_id?: string; customer_id?: string; item_id?: string; tax_id?: string;
  party_ledger?: string; purchase_ledger?: string; sales_ledger?: string;
  cgst_ledger?: string; sgst_ledger?: string; igst_ledger?: string;
};

export type ReviewWorkspace = {
  findings: { code: string; severity: "ERROR" | "WARNING"; field_key?: string; message: string }[];
  evidence: { field_key: string; page?: number; region?: unknown; evidence_text?: string; provider?: string }[];
  drafts: { provider: string; status: string; version: number; validation_state: string; totals: Record<string, number> }[];
  connectors: { provider: "ZOHO_BOOKS" | "TALLY_PRIME"; status: string }[];
};

export async function getReviewWorkspace(id: string): Promise<ReviewWorkspace> {
  const res = await fetch(`/api/documents/${id}/workspace`, { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error("Could not load validation and connector status");
  return res.json();
}

export async function postToBooks(id: string, mapping: DocumentMapping = {}): Promise<DocumentActionProposal> {
  const res = await fetch(`/api/documents/${id}/post`, {
    method: "POST",
    headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(mapping),
  });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const errBody = await res.json();
      if (errBody.detail) msg = errBody.detail;
    } catch {
      // ignore
    }
    throw new Error(msg);
  }
  return res.json();
}

export async function approveDocumentAction(actionId: string, payloadHash: string) {
  const res = await fetch(`/api/agent/actions/${actionId}/approve`, {
    method: "POST",
    headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ payload_hash: payloadHash }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Could not approve action: ${res.statusText}`);
  }
  return res.json() as Promise<{ status: string; external_reference_id?: string }>;
}

export async function rejectDocument(id: string, reason: string): Promise<ExtractedDocument> {
  const res = await fetch(`/api/documents/${id}/reject`, {
    method: "POST",
    headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
  if (!res.ok) throw new Error(`Failed to reject document: ${res.statusText}`);
  return res.json();
}

export async function markNeedsInfo(id: string): Promise<ExtractedDocument> {
  const res = await fetch(`/api/documents/${id}/needs-info`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to mark needs info: ${res.statusText}`);
  return res.json();
}

export async function uploadDocument(file: File, clientId: string, clientName: string): Promise<ExtractedDocument> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("client_id", clientId);
  formData.append("client_name", clientName);

  const headers = await getAuthHeaders();
  delete headers["Content-Type"]; // Let the browser set the boundary for multipart/form-data

  // Use Next.js API proxy for uploads
  const res = await fetch(`/api/documents/upload`, {
    method: "POST",
    headers,
    body: formData,
  });
  
  if (!res.ok) throw new Error(`Failed to upload document: ${res.statusText}`);
  return res.json();
}
