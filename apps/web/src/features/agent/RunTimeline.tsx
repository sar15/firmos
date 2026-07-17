import { Check, Circle, Loader2 } from "lucide-react";
import { AgentAction } from "./agent.api";

export function RunTimeline({ action }: { action: AgentAction }) {
  return (
    <ol aria-label="Execution timeline" className="mt-3 grid gap-2 sm:grid-cols-3">
      {action.run_timeline.map((item) => (
        <li key={item.stage} className="flex min-h-11 items-center gap-2 rounded-[6px] border border-[var(--hairline)] bg-[var(--panel)] px-3 py-2">
          {item.state === "complete" ? (
            <Check className="h-4 w-4 text-[var(--royal)]" aria-hidden="true" />
          ) : item.state === "active" ? (
            <Loader2 className="h-4 w-4 animate-spin text-[var(--royal)] motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <Circle className="h-4 w-4 text-[var(--muted-2)]" aria-hidden="true" />
          )}
          <span className="text-xs capitalize text-[var(--text-2)]">{item.stage.replaceAll("_", " ").toLowerCase()}</span>
        </li>
      ))}
    </ol>
  );
}
