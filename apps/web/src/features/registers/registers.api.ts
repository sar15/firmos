import { SalesRegisterRow, SalesRegisterRowSchema, PurchaseRegisterRow } from "./registers.types";
import { getAuthHeaders } from "@/lib/auth";

export const getSalesRegister = async (clientId: string, period?: string): Promise<SalesRegisterRow[]> => {
  const params = new URLSearchParams({ client_id: clientId });
  if (period) params.append("period", period);
  const res = await fetch(`/api/registers/sales?${params.toString()}`, {
    headers: await getAuthHeaders(),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`Sales register could not be loaded (${res.status}).`);
  const data = await res.json();
  return Array.isArray(data) ? data.map(row => SalesRegisterRowSchema.parse(row)) : [];
};

export const getPurchaseRegister = async (clientId: string, period?: string): Promise<PurchaseRegisterRow[]> => {
  try {
    const params = new URLSearchParams({ client_id: clientId });
    if (period) params.append("period", period);
    const res = await fetch(`/api/registers/purchase?${params.toString()}`, {
      headers: await getAuthHeaders(),
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch (error) {
    console.warn("Failed to fetch purchase register:", error);
    return [];
  }
};

export type RegisterStatus = { state: "RUNNING" | "PARTIAL" | "COMPLETE" | "MISMATCH" | "FAILED"; message?: string; complete_through?: string };

export async function getPurchaseRegisterStatus(clientId: string, period: string): Promise<RegisterStatus> {
  const params = new URLSearchParams({ client_id: clientId, period });
  const res = await fetch(`/api/registers/purchase/status?${params}`, { headers: await getAuthHeaders(), cache: "no-store" });
  if (!res.ok) return { state: "PARTIAL", message: "Freshness could not be verified." };
  return res.json();
}

export async function getSalesRegisterStatus(clientId: string, period: string): Promise<RegisterStatus> {
  const params = new URLSearchParams({ client_id: clientId, period });
  const res = await fetch(`/api/registers/sales/status?${params}`, { headers: await getAuthHeaders(), cache: "no-store" });
  if (!res.ok) return { state: "PARTIAL", message: "Freshness could not be verified." };
  return res.json();
}

export async function syncZohoRegisters(clientId: string, period: string): Promise<void> {
  const params = new URLSearchParams({ client_id: clientId, period });
  const res = await fetch(`/api/registers/sync?${params.toString()}`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Register sync failed: ${res.statusText}`);
}
