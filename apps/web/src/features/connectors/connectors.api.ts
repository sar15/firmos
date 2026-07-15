import { Category } from "@/types";
import { getAuthHeaders } from "@/lib/auth";

export interface SetupReadiness {
  production_ready: boolean;
  checks: { id: string; label: string; ready: boolean; detail?: string }[];
}

export interface ZohoOrganizationChoice {
  attempt_id: string;
  organizations: { organization_id: string; name: string }[];
}

export async function getConnectors(): Promise<Category[]> {
  const res = await fetch("/api/connectors", { headers: await getAuthHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to get connectors: ${res.statusText}`);
  return res.json();
}

export async function getSetupReadiness(): Promise<SetupReadiness> {
  const res = await fetch("/api/setup/readiness", { headers: await getAuthHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to check setup readiness: ${res.statusText}`);
  return res.json();
}

export async function getZohoOrganizationChoice(attemptId: string): Promise<ZohoOrganizationChoice> {
  const res = await fetch(`/api/connectors/c1/organization-choice/${encodeURIComponent(attemptId)}`, { headers: await getAuthHeaders(), cache: "no-store" });
  if (!res.ok) throw new Error("This Zoho connection request is no longer available. Start again.");
  return res.json();
}

export async function selectZohoOrganization(attemptId: string, organizationId: string, clientId: string): Promise<{ status: string; organization_name: string }> {
  const res = await fetch(`/api/connectors/c1/organization-choice/${encodeURIComponent(attemptId)}`, {
    method: "POST",
    headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ organization_id: organizationId, client_id: clientId }),
  });
  if (!res.ok) throw new Error("Zoho could not be connected. Please try again.");
  return res.json();
}
