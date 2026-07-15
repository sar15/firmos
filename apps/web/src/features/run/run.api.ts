// Run execution seam — workflow run details + activity log

import { getAuthHeaders } from "../../lib/auth";

export type RunStepStatus = "COMPLETED" | "IN_PROGRESS" | "PENDING";

export interface RunStep {
  id: string;
  timestamp: string;
  status: RunStepStatus;
  description: string;
}

export interface RunExecution {
  id: string;
  title: string;
  clientName: string;
  workflowType: "VENDOR_BILL" | "BANK_RECON" | "GSTR2B" | "GSTR3B";
  status: "RUNNING" | "AWAITING_APPROVAL" | "AWAITING_OTP" | "AWAITING_MANUAL_FILING" | "COMPLETED" | "FAILED";
  steps: RunStep[];
  startedAt: string;
  completedAt: string | null;
  draftData?: unknown;
}

interface WorkflowState {
  status?: string;
  client_id?: string;
  audit_entries?: Array<{ description?: string }>;
  gstr3b_draft?: unknown;
}

interface WorkflowResponse {
  state?: WorkflowState;
  next?: string[];
  created_at?: string;
}

export async function getRunExecution(id: string): Promise<RunExecution | null> {
  const res = await fetch(`/api/workflows/t4/run/${id}`, { headers: await getAuthHeaders() });
  if (!res.ok) return null;
  
  const data = await res.json() as WorkflowResponse;
  if (!data.state) return null;

  const state = data.state;
  let status: RunExecution["status"] = "RUNNING";
  if (state.status === "AWAITING_MANUAL_FILING") status = "AWAITING_MANUAL_FILING";
  else if (data.next && data.next.includes("otp_gate")) status = "AWAITING_OTP";
  else if (data.next && data.next.length > 0) status = "AWAITING_APPROVAL";
  
  const steps: RunStep[] = [];
  
  if (state.audit_entries) {
    state.audit_entries.forEach((audit, index) => {
      steps.push({
        id: `s${index}`,
        timestamp: new Date().toLocaleTimeString(),
        status: "COMPLETED",
        description: audit.description ?? "Workflow activity"
      });
    });
  }
  
  if (status === "AWAITING_APPROVAL") {
    steps.push({
      id: "pending_gate",
      timestamp: "",
      status: "IN_PROGRESS",
      description: "Awaiting human approval"
    });
  } else if (status === "AWAITING_OTP") {
    steps.push({
      id: "pending_otp",
      timestamp: "",
      status: "IN_PROGRESS",
      description: "Awaiting EVC OTP from CA"
    });
  } else if (status === "AWAITING_MANUAL_FILING") {
    steps.push({
      id: "manual_filing",
      timestamp: "",
      status: "IN_PROGRESS",
      description: "Manual portal filing required; add acknowledgement evidence when complete"
    });
  }

  return {
    id,
    title: "GSTR-3B Workflow",
    clientName: state.client_id || "Unknown Client",
    workflowType: "GSTR3B",
    status,
    startedAt: data.created_at || new Date().toISOString(),
    completedAt: null,
    steps,
    draftData: state.gstr3b_draft,
  };
}

export async function approveRunExecution(id: string, approvalData: Record<string, unknown> = { approved: true }): Promise<boolean> {
  const res = await fetch(`/api/workflows/t4/resume`, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify({
      thread_id: id,
      approval_data: approvalData
    })
  });
  return res.ok;
}
