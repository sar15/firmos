import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "w-full py-12 flex flex-col items-center justify-center border border-dashed border-[var(--hairline)] rounded-[6px] bg-[var(--canvas)]",
        className
      )}
    >
      <div className="w-10 h-10 rounded-full bg-[var(--hover)] flex items-center justify-center mb-4">
        <Icon className="w-5 h-5 text-[var(--muted-2)]" strokeWidth={1.5} />
      </div>
      <h3 className="text-[14px] font-semibold text-[var(--text)] mb-1">{title}</h3>
      <p className="text-[13px] text-[var(--muted)] text-center max-w-[280px] mb-5">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
}
