"use client";

import React from "react";
import { CheckCircle2, Clock3 } from "lucide-react";
import { ActionButton } from "@/components/actions/ActionButton";
import { AgentAction, approveAgentAction, cancelAgentAction } from "./agent.api";
import { PlanPreview } from "./PlanPreview";
import { RunTimeline } from "./RunTimeline";

const primary = "min-h-11 rounded-[6px] border border-[var(--royal)] bg-[var(--royal)] px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-[var(--royal-hover)] disabled:cursor-not-allowed disabled:opacity-50";
const secondary = "min-h-11 rounded-[6px] border border-[var(--hairline)] bg-white px-4 py-2 text-sm font-medium text-[var(--red)] transition-colors hover:bg-[var(--red-tint)] disabled:cursor-not-allowed disabled:opacity-50";

export function ApprovalCard({ action, onChanged }: { action: AgentAction; onChanged?: () => void }) {
  const [status, setStatus] = React.useState(action.status);
  const provider = action.provider === "ZOHO_BOOKS" ? "Zoho Books" : "Tally Prime";
  const awaiting = status === "AWAITING_APPROVAL";

  if (!awaiting) {
    const complete = status === "SUCCEEDED";
    return (
      <article className="rounded-[6px] border border-[var(--hairline)] bg-white p-4">
        <div className="flex items-start gap-3">
          {complete ? <CheckCircle2 className="mt-0.5 h-5 w-5 text-[var(--royal)]" /> : <Clock3 className="mt-0.5 h-5 w-5 text-[var(--royal)]" />}
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[var(--text)]">{provider} · {status.replaceAll("_", " ").toLowerCase()}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{action.operation}</p>
            <p className="mt-1 font-mono text-[11px] text-[var(--muted-2)]">Run {action.correlation_id || action.id}</p>
          </div>
        </div>
        <RunTimeline action={action} />
      </article>
    );
  }

  const changed = (next: { status: string }) => {
    setStatus(next.status);
    onChanged?.();
  };

  return (
    <article className="rounded-[6px] border border-[var(--royal-tint-2)] bg-white p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-[var(--royal)]">Approval required</p>
        <span className="rounded-full bg-[var(--red-tint)] px-2 py-0.5 text-xs font-medium text-[var(--red)]">High-risk write</span>
      </div>
      <h3 className="mt-2 text-base font-semibold text-[var(--text)]">Create one reviewed purchase object in {provider}</h3>
      <p className="mt-1 text-sm text-[var(--muted)]">Review the exact plan and financial change. Approval binds to payload hash {action.payload_hash.slice(0, 10)}…</p>
      <PlanPreview action={action} />
      <div className="mt-4 flex flex-wrap gap-2">
        <ActionButton
          capabilityKey={action.operation}
          requiredPermission="books.approve"
          mutation={() => approveAgentAction(action.id, action.payload_hash)}
          loadingLabel="Approving…"
          confirmationPolicy={{ kind: "confirm", message: `Approve this immutable ${provider} write?` }}
          idempotencyKey={action.id}
          correlationId={action.correlation_id}
          successEvidence={(result) => `Queued safely · action ${result.id}`}
          disabledReason={action.disabled_reason}
          onSuccess={changed}
          className={primary}
        >
          Approve and queue
        </ActionButton>
        <ActionButton
          capabilityKey={action.operation}
          requiredPermission="books.approve"
          mutation={() => cancelAgentAction(action.id)}
          loadingLabel="Rejecting…"
          confirmationPolicy={{ kind: "confirm", message: "Reject this proposal? It will not reach the provider." }}
          correlationId={action.correlation_id}
          successEvidence={(result) => `Rejected · action ${result.id}`}
          disabledReason={action.disabled_reason}
          onSuccess={changed}
          className={secondary}
        >
          Reject
        </ActionButton>
      </div>
    </article>
  );
}
