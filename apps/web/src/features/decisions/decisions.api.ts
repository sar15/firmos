import { Decision } from "@/types";
import { getAuthHeaders } from "@/lib/auth";

export async function getDecisions(): Promise<Decision[]> {
  const res = await fetch(`/api/decisions`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch decisions");
  return res.json();
}

export async function getDecision(id: string): Promise<Decision> {
  const res = await fetch(`/api/decisions/${id}`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch decision");
  return res.json();
}

export async function getDecisionContext(id: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/decisions/${id}/context`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch decision context");
  return res.json();
}

export async function draftDecisionResponse(id: string, instructions?: string): Promise<Record<string, unknown>> {
  const res = await fetch(`/api/decisions/${id}/draft`, {
    method: "POST",
    headers: {
      ...await getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ instructions }),
  });
  if (!res.ok) throw new Error("Failed to draft decision response");
  return res.json();
}

export async function approveDecision(id: string, reviewedResponse: string): Promise<Decision> {
  const res = await fetch(`/api/decisions/${id}/approve`, {
    method: "POST",
    headers: {
      ...await getAuthHeaders(),
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ reviewed_response: reviewedResponse }),
  });
  if (!res.ok) throw new Error("Failed to approve decision");
  return res.json();
}

export async function rejectDecision(id: string): Promise<Decision> {
  const res = await fetch(`/api/decisions/${id}/reject`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to reject decision");
  return res.json();
}
