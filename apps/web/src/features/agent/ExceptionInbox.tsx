import { AlertTriangle } from "lucide-react";
import { AgentException } from "./agent.api";

export function ExceptionInbox({ exceptions }: { exceptions: AgentException[] }) {
  if (!exceptions.length) return null;
  return (
    <section aria-labelledby="agent-exceptions" className="rounded-xl border border-[var(--amber-border)] bg-[var(--amber-tint)] p-4">
      <div className="flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-[var(--amber)]" aria-hidden="true" />
        <h2 id="agent-exceptions" className="text-sm font-semibold text-[var(--text)]">Needs attention</h2>
        <span className="ml-auto rounded-full bg-white px-2 py-0.5 font-mono text-xs text-[var(--muted)]">{exceptions.length}</span>
      </div>
      <div className="mt-3 grid gap-2">
        {exceptions.slice(0, 5).map((item) => (
          <article key={item.action_id} className="rounded-lg border border-[var(--amber-border)] bg-white p-3">
            <p className="text-sm font-medium text-[var(--text)]">{item.status.replaceAll("_", " ").toLowerCase()}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{item.recovery_action}</p>
            {item.correlation_id && <p className="mt-1 font-mono text-[11px] text-[var(--muted-2)]">Run {item.correlation_id}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}
