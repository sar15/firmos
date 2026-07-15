"use client";

import React from "react";
import { ChatGreeting } from "./ChatGreeting";
import { StepCard } from "./StepCard";
import { ApprovalCard } from "./ApprovalCard";
import { AgentComposer } from "./AgentComposer";
import { AgentContext, fetchChatSession, getAgentContext, TimelineItem } from "./agent.api";
import { Client } from "@/types";
import { formatIndianRupee } from "@/lib/formatIndianRupee";
import { ExceptionInbox } from "./ExceptionInbox";

export function AgentChat() {
  const [timeline, setTimeline] = React.useState<TimelineItem[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [client, setClient] = React.useState<Client | null>(null);
  const [context, setContext] = React.useState<AgentContext | null>(null);
  const [period, setPeriod] = React.useState(() => {
    const today = new Date();
    return `${String(today.getMonth() + 1).padStart(2, "0")}${today.getFullYear()}`;
  });

  const fetchTimeline = React.useCallback((clientId = client?.id) => {
    if (!clientId) {
      setTimeline([]);
      setContext(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    Promise.all([fetchChatSession(clientId), getAgentContext(clientId, period)])
      .then(([timelineData, contextData]) => {
        setTimeline(timelineData);
        setContext(contextData);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch session", err);
        setLoading(false);
      });
  }, [client?.id, period]);

  React.useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  return (
    <div className="flex-1 flex flex-col min-h-0 relative">
      <div className="flex-1 overflow-y-auto px-6 pt-8 pb-32">
        <div className="max-w-[720px] mx-auto flex flex-col gap-6">
          <ChatGreeting />
          <section className="rounded-xl border border-[var(--hairline)] bg-white p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div><p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Finance workspace</p><p className="mt-1 text-sm text-[var(--muted)]">{client ? <>Working with <strong className="text-[var(--text)]">{client.legalName}</strong>. Every write needs approval.</> : <>Choose a client with <strong className="text-[var(--text)]">@</strong> to load live evidence.</>}</p></div>
              <label className="flex items-center gap-2 text-sm text-[var(--muted)]">Period<input aria-label="Workspace period" type="month" value={`${period.slice(2)}-${period.slice(0, 2)}`} onChange={(event) => { const [year, month] = event.target.value.split("-"); if (year && month) setPeriod(`${month}${year}`); }} className="h-10 rounded-md border border-[var(--hairline)] px-2 text-[var(--text)]" /></label>
            </div>
            {context && <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <Metric label="Sales register" value={formatIndianRupee(context.sales.total_paise)} detail={`${context.sales.count} entries`} />
              <Metric label="Purchase register" value={formatIndianRupee(context.purchases.total_paise)} detail={`${context.purchases.count} entries`} />
              <Metric label="Recent actions" value={String(context.recent_actions.length)} detail="Reviewable provider actions" />
            </div>}
          </section>
          {context && <ExceptionInbox exceptions={context.exceptions} />}
          {context && context.recent_actions.length > 0 && (
            <section aria-labelledby="agent-runs" className="grid gap-3">
              <div className="flex items-center justify-between">
                <h2 id="agent-runs" className="text-sm font-semibold text-[var(--text)]">Plans and runs</h2>
                <span className="font-mono text-xs text-[var(--muted)]">{context.recent_actions.length}</span>
              </div>
              {context.recent_actions.map((action) => (
                <ApprovalCard key={action.id} action={action} onChanged={() => fetchTimeline()} />
              ))}
            </section>
          )}
          
          {loading ? (
            <div className="text-[var(--muted-2)] text-[13px]">Loading timeline...</div>
          ) : (
            timeline.map((item) => {
              if (item.type === "message") {
                return (
                  <div key={item.id} className="flex gap-4">
                    <div className="w-8 h-8 rounded-[6px] bg-[var(--hover)] border border-[var(--hairline)] shrink-0 flex items-center justify-center font-mono font-semibold text-[11px] text-[var(--royal)]">
                      {item.role === "agent" ? "fOS" : "CA"}
                    </div>
                    <div className="flex-1 pt-1.5">
                      <div className="text-[13px] text-[var(--text)] leading-relaxed">
                        {item.text}
                      </div>
                    </div>
                  </div>
                );
              }

              if (item.type === "audit_entry") {
                return (
                  <div key={item.id} className="mt-2 border border-[var(--hairline)] rounded-[6px] overflow-hidden bg-white">
                    <StepCard entry={{
                      id: item.id,
                      action: item.action,
                      description: typeof item.details?.description === "string" ? item.details.description : item.action,
                      time: new Date(item.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                      details: JSON.stringify(item.details, null, 2),
                      status: item.action === "STEP_FAILED" ? "err" : "done"
                    }} />
                  </div>
                );
              }

              return null;
            })
          )}

          {timeline.length === 0 && !loading && (
            <div className="rounded-md border border-dashed border-[var(--hairline)] bg-white p-5 text-sm text-[var(--muted)]">No activity yet. Upload a GSTR-2B file or propose a reviewed accounting action to begin.</div>
          )}

        </div>
      </div>
      <AgentComposer client={client} period={period} onClientSelected={setClient} onMessageSent={() => fetchTimeline()} />
    </div>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="rounded-lg bg-[var(--hover)] p-3"><p className="text-xs text-[var(--muted)]">{label}</p><p className="mt-1 font-mono text-lg font-semibold text-[var(--text)]">{value}</p><p className="mt-1 text-xs text-[var(--muted)]">{detail}</p></div>;
}
