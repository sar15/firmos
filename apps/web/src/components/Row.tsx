import { cn } from "@/lib/utils";

interface RowProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  interactive?: boolean;
}

export function Row({ children, className, interactive = true, ...props }: RowProps) {
  return (
    <div 
      className={cn(
        "flex items-center justify-between py-2 border-b border-hairline px-2 -mx-2 rounded-[6px] transition-all duration-120 group",
        interactive && "hover:bg-hover cursor-pointer btn-tactile focus-ring",
        className
      )}
      tabIndex={interactive ? 0 : undefined}
      {...props}
    >
      <div className="flex-1 flex items-center justify-between">
        {children}
      </div>
      {interactive && (
        <span className="text-muted-2 opacity-0 group-hover:opacity-100 transition-opacity translate-x-1 group-hover:translate-x-0 duration-150 ml-3">
          ›
        </span>
      )}
    </div>
  );
}
