import { AuditEntry } from "@/types";
import { getAuthHeaders } from "@/lib/auth";

export interface AuditFilter {
  actor?: "firmOS" | "HUMAN";
  action?: string;
  search?: string;
}

interface AuditApiRow {
  id: string;
  createdAt: string;
  actor: string;
  action: AuditEntry["action"];
  details?: { description?: string; confidence?: number };
}

export async function listAuditEntries(filter?: AuditFilter): Promise<AuditEntry[]> {
  const res = await fetch(`/api/audit`, {
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error("Failed to fetch audit logs");
  
  const rawData = await res.json();
  
  let result: AuditEntry[] = (rawData as AuditApiRow[]).map((row) => ({
    id: row.id,
    timestamp: row.createdAt,
    actor: row.actor === "system" ? "firmOS" : "HUMAN",
    actorName: row.actor === "system" ? "firmOS" : row.actor,
    action: row.action,
    description: row.details?.description || "Action performed",
    confidence: row.details?.confidence || null,
  }));

  if (filter?.actor) {
    result = result.filter((e) => e.actor === filter.actor);
  }
  if (filter?.action) {
    result = result.filter((e) => e.action === filter.action);
  }
  if (filter?.search) {
    const q = filter.search.toLowerCase();
    result = result.filter((e) =>
      e.description.toLowerCase().includes(q) ||
      e.actorName.toLowerCase().includes(q)
    );
  }

  return result;
}
