import { ConfidenceLevel } from "@/types";
import { cn } from "@/lib/utils";
import { Check } from "lucide-react";

interface ConfidenceBadgeProps {
  level: ConfidenceLevel;
  className?: string;
  showLabel?: boolean; // Kept for backwards compatibility if used elsewhere
}

export function ConfidenceBadge({ level, className, showLabel = true }: ConfidenceBadgeProps) {
  if (level === "HIGH") {
    return (
      <div className={cn("inline-flex items-center gap-1 text-[var(--muted)]", className)} title={showLabel ? "High confidence" : undefined}>
        <Check className="w-3.5 h-3.5" />
      </div>
    );
  }

  if (level === "REVIEW") {
    return (
      <div className={cn("inline-flex items-center px-1.5 py-0.5 rounded-[4px] border border-[var(--amber)] text-[var(--amber)] text-[10px] font-bold uppercase tracking-wider", className)}>
        {showLabel ? "Review" : "!"}
      </div>
    );
  }

  if (level === "LOW") {
    return (
      <div className={cn("inline-flex items-center px-1.5 py-0.5 rounded-[4px] border border-[var(--red)] text-[var(--red)] text-[10px] font-bold uppercase tracking-wider", className)}>
        {showLabel ? "Low" : "!"}
      </div>
    );
  }

  return null;
}
