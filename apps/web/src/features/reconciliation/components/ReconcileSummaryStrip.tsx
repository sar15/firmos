import React from "react";
import { formatIndianRupee } from "@/lib/formatIndianRupee";
import { StatusDot } from "@/components/StatusDot";
import { Button } from "@/components/ui/button";

interface SummaryProps {
  summary: {
    autoMatched: number;
    suggested: number;
    unmatched: number;
    totalAutoMatched: number;
    totalSuggested: number;
    totalUnmatched: number;
  };
  onBulkAcceptClean: () => void;
  isAccepting: boolean;
}

export function ReconcileSummaryStrip({ summary, onBulkAcceptClean, isAccepting }: SummaryProps) {
  const totalItems = summary.autoMatched + summary.suggested + summary.unmatched;
  
  return (
    <div className="flex items-center justify-between px-6 py-3 bg-[var(--canvas)] border-b border-[var(--hairline)] shrink-0 z-10">
      <div className="flex items-center gap-8">
        <div className="flex flex-col">
          <span className="text-xs text-muted font-medium uppercase tracking-wider mb-1">To Review</span>
          <div className="flex items-center gap-2">
            <StatusDot color="amber" />
            <span className="font-mono text-sm text-slate-700 font-medium">{summary.suggested}</span>
            <span className="text-sm text-muted-2">({formatIndianRupee(summary.totalSuggested)})</span>
          </div>
        </div>

        <div className="flex flex-col">
          <span className="text-xs text-muted font-medium uppercase tracking-wider mb-1">Unmatched</span>
          <div className="flex items-center gap-2">
            <StatusDot color="red" />
            <span className="font-mono text-sm text-slate-700 font-medium">{summary.unmatched}</span>
            <span className="text-sm text-muted-2">({formatIndianRupee(summary.totalUnmatched)})</span>
          </div>
        </div>

        <div className="flex flex-col">
          <span className="text-xs text-muted font-medium uppercase tracking-wider mb-1">Auto-Matched</span>
          <div className="flex items-center gap-2">
            <StatusDot color="royal" />
            <span className="font-mono text-sm text-slate-700 font-medium">{summary.autoMatched}</span>
            <span className="text-sm text-muted-2">({formatIndianRupee(summary.totalAutoMatched)})</span>
          </div>
        </div>
      </div>
      
      <div className="flex items-center gap-4">
        <span className="text-sm text-muted">
          <span className="font-mono">{totalItems}</span> total lines
        </span>
        <Button 
          onClick={onBulkAcceptClean}
          disabled={summary.suggested === 0 || isAccepting}
          className="bg-[var(--royal)] hover:bg-[var(--royal)]/90 text-white"
        >
          {isAccepting ? "Accepting..." : "Accept all clean"}
        </Button>
      </div>
    </div>
  );
}
