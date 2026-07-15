import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { ClientProfile } from "@/features/clients/clients.api";

export function ActiveWorkflows({ decisions }: { decisions: ClientProfile["recentDecisions"] }) {
  if (!decisions || decisions.length === 0) return null;

  return (
    <div className="w-full mb-8">
      <h2 className="text-[11px] font-semibold text-muted tracking-widest uppercase mb-2">
        Active Workflows
      </h2>
      <div className="flex flex-col border-t border-hairline">
        {decisions.map((decision) => (
          <Link 
            key={decision.id}
            href={`/decisions/${decision.id}`} 
            className="flex items-center justify-between py-3 hover:bg-hover transition-all duration-150 group cursor-pointer px-2 -mx-2 rounded-[6px]"
          >
            <div className="flex items-center gap-3">
              <span className="font-medium text-text text-[13px] leading-tight group-hover:text-royal transition-colors">
                {decision.task}
              </span>
              <span className="text-[var(--hairline)]">•</span>
              <span className="text-[12px] text-[var(--amber)] font-medium">
                {decision.status === "pending" ? "Awaiting your approval" : decision.status}
              </span>
            </div>
            <ArrowRight className="w-4 h-4 text-[var(--hairline)] group-hover:text-muted transition-all duration-150" />
          </Link>
        ))}
      </div>
    </div>
  );
}
