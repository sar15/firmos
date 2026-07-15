import { getAuthHeaders } from "@/lib/auth";
import { requireJson } from "@/lib/api/errors";

export interface AuditEntry {
  id: string;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  createdAt: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "agent";
  text: string;
  createdAt: string;
}

export interface AgentPlanStep {
  operation_key: string;
  client_id: string;
  period: string;
  input_source_ids: string[];
  required_capability: string;
  read_write_risk: "WRITE_HIGH";
  expected_output: string;
  approval_policy: "EXPLICIT_CA_APPROVAL";
  dependencies: string[];
  rollback_recovery: string;
}

export interface FinancialDiff {
  kind: "NEW_OBJECT";
  before: null;
  after: Record<string, unknown>;
  taxes: Record<string, number>;
  total_paise: number | null;
  evidence_ids: string[];
}

export interface AgentAction {
  id: string;
  client_id: string;
  provider: "ZOHO_BOOKS" | "TALLY_PRIME";
  operation: string;
  status: string;
  payload_hash: string;
  risk_level: string;
  correlation_id: string;
  external_reference_id?: string | null;
  created_at: string;
  updated_at: string;
  plan_step: AgentPlanStep;
  financial_diff: FinancialDiff;
  run_timeline: { stage: string; state: "complete" | "active" | "pending" }[];
  disabled_reason?: string | null;
}

export interface AgentException {
  action_id: string;
  status: string;
  priority: number;
  operation: string;
  recovery_action: string;
  correlation_id: string;
}

export type TimelineItem = 
  | (ChatMessage & { type: "message" })
  | (AuditEntry & { type: "audit_entry" });

export interface AgentContext {
  period: string;
  sales: { count: number; total_paise: number };
  purchases: { count: number; total_paise: number };
  recent_actions: AgentAction[];
  exceptions: AgentException[];
}

export async function getAgentContext(clientId: string, period: string): Promise<AgentContext> {
  const res = await fetch(`/api/agent/clients/${encodeURIComponent(clientId)}/context?period=${encodeURIComponent(period)}`, { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error("Failed to load client context");
  return res.json();
}

export async function fetchChatSession(clientId: string): Promise<TimelineItem[]> {
  const res = await fetch(`/api/chat/session/${encodeURIComponent(clientId)}`, {
    headers: await getAuthHeaders(),
  });

  if (!res.ok) {
    throw new Error("Failed to fetch chat session");
  }

  const data = await res.json();
  return Array.isArray(data) ? data : (data.timeline || []);
}

export async function sendChatMessage(clientId: string, period: string, text: string): Promise<void> {
  const res = await fetch(`/api/chat/session`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify({ client_id: clientId, period, text }),
  });

  if (!res.ok) {
    throw new Error("Failed to send chat message");
  }
}

export interface ActionMutationResult {
  id: string;
  status: string;
  correlation_id?: string;
  external_reference_id?: string | null;
}

export async function approveAgentAction(actionId: string, payloadHash: string): Promise<ActionMutationResult> {
  const res = await fetch(`/api/agent/actions/${encodeURIComponent(actionId)}/approve`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify({ payload_hash: payloadHash }),
  });
  return requireJson<ActionMutationResult>(res);
}

export async function cancelAgentAction(actionId: string): Promise<ActionMutationResult> {
  const res = await fetch(`/api/agent/actions/${encodeURIComponent(actionId)}/cancel`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  return requireJson<ActionMutationResult>(res);
}
