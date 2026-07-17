import React from "react";
import type { ReconLine, ReconMatch } from "@/types";
import { formatIndianRupee } from "@/lib/formatIndianRupee";
import { formatComplianceDate } from "@/lib/formatComplianceDate";
import { cn } from "@/lib/utils";
import { Check, X, Undo2 } from "lucide-react";

interface MatchRowProps {
  match: ReconMatch;
  isFocused?: boolean;
  onAccept?: (id: string) => void;
  onReject?: (id: string) => void;
  onUndo?: (id: string) => void;
}

export function MatchRow({ 
  match, 
  isFocused, 
  onAccept, 
  onReject, 
  onUndo 
}: MatchRowProps) {
  const { source, target, status, score, flag, reasons } = match;

  const renderSide = (line?: ReconLine | null, isSource?: boolean) => {
    if (!line) return (
      <div className="flex-1 flex items-center justify-start px-4 opacity-50 italic text-[13px] text-[var(--muted-2)]">
        No matching record
      </div>
    );
    
    return (
      <div className="flex-1 flex flex-col justify-center px-4 py-2 h-full min-w-0">
        <div className="flex justify-between items-center mb-0.5 w-full">
          <span className="font-medium text-[var(--text)] text-[13px] truncate pr-4" title={line.description}>
            {line.description}
          </span>
          <span className="font-mono text-[13px] font-medium text-[var(--text)] shrink-0 tabular-nums text-right">
            {formatIndianRupee(line.amount)}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[12px] text-[var(--muted)]">
          <span className="font-mono">{formatComplianceDate(line.date)}</span>
          <span>·</span>
          <span className="truncate max-w-[150px]">{line.counterparty}</span>
          {line.ref && (
            <>
              <span>·</span>
              <span className="font-mono text-[10px] bg-[var(--hover)] px-1 py-0.5 rounded border border-[var(--hairline)]">{line.ref}</span>
            </>
          )}
        </div>
        {!isSource && flag && (
          <div className="mt-1">
            <span className="inline-flex text-[10px] font-bold uppercase px-1.5 py-0.5 rounded-[4px] border border-[var(--hairline)] bg-[var(--hover)] text-[var(--muted)] tracking-wider">
              {flag.replace(/_/g, " ")}
            </span>
          </div>
        )}
      </div>
    );
  };

  const getScoreColor = (sc?: number) => {
    if (sc === undefined) return "text-[var(--muted)]";
    if (sc >= 0.9) return "text-[var(--muted)]";
    if (sc >= 0.6) return "text-[var(--amber)]";
    return "text-[var(--red)]";
  };

  return (
    <div 
      className={cn(
        "grid grid-cols-1 sm:grid-cols-[1fr_1fr_128px] min-h-[76px] border-b border-[var(--hairline)] bg-[var(--canvas)] transition-colors duration-150 group relative",
        isFocused ? "bg-[var(--hover)] ring-1 ring-inset ring-[var(--royal)] z-10" : "hover:bg-[var(--hover)]"
      )}
    >
      {/* SOURCE Pane (Left) */}
      <div className="border-r border-[var(--hairline)] flex flex-col justify-center min-w-0">
        {renderSide(source, true)}
      </div>

      {/* TARGET Pane (Middle) */}
      <div className="flex flex-col justify-center border-r border-[var(--hairline)] min-w-0">
        {renderSide(target, false)}
        {reasons?.[0] && <p className="px-4 pb-2 text-xs leading-5 text-[var(--muted)]">Why: {reasons[0]}</p>}
      </div>

      {/* ACTION ZONE (Right - Fixed 96px) */}
      <div className="flex min-h-12 items-center justify-end border-t border-[var(--hairline)] px-3 gap-2 relative sm:border-t-0">
        {status === "SUGGESTED" && (
          <div className="flex items-center gap-2.5 w-full justify-end">
            <span className={cn("text-[11px] font-mono font-medium shrink-0", getScoreColor(score))}>
              {score ? (score * 100).toFixed(0) + "%" : "??%"}
            </span>
            <div className={cn("flex items-center gap-1 shrink-0 transition-opacity duration-150", isFocused ? "opacity-100" : "opacity-35 group-hover:opacity-100")}>
              <button 
                className="flex items-center justify-center size-11 cursor-pointer rounded-full text-[var(--muted)] hover:text-[var(--red)] hover:bg-[var(--red)]/10 transition-colors focus-ring"
                onClick={() => onReject && onReject(match.id)}
                title="Reject (X)"
                aria-label="Reject suggested match"
              >
                <X className="h-4 w-4" />
              </button>
              <button 
                className="flex items-center justify-center size-11 cursor-pointer rounded-full text-[var(--muted)] hover:text-[var(--royal)] hover:bg-[var(--royal-tint)] transition-colors focus-ring"
                onClick={() => onAccept && onAccept(match.id)}
                title="Accept (A)"
                aria-label="Accept suggested match"
              >
                <Check className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {status === "UNMATCHED" && <span className="text-[11px] text-[var(--muted)]">{source ? "Review" : "Portal-only entry"}</span>}

        {status === "AUTO_MATCHED" && (
          <div className="flex items-center justify-end w-full">
            <div className="hidden items-center gap-1 text-[11px] font-bold text-[var(--muted)] uppercase tracking-wider sm:flex sm:group-hover:hidden">
              <Check className="h-3.5 w-3.5" />
              Matched
            </div>
            <button
              className="flex min-h-11 cursor-pointer items-center justify-center px-3 rounded-[6px] text-[11px] font-medium text-[var(--muted)] hover:text-[var(--text)] hover:bg-[var(--hover)] transition-colors gap-1.5 border border-transparent hover:border-[var(--hairline)] w-full sm:hidden sm:group-hover:flex"
              onClick={() => onUndo && onUndo(match.id)}
              aria-label="Undo accepted match"
            >
              <Undo2 className="h-3 w-3" />
              Undo
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
