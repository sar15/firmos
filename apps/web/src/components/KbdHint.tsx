import { cn } from "@/lib/utils";

interface KbdHintProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
}

export function KbdHint({ children, className, ...props }: KbdHintProps) {
  return (
    <span 
      className={cn(
        "px-1 py-0.5 rounded-[4px] border border-hairline bg-hover text-[10px] font-mono text-muted-2 uppercase tracking-widest leading-none",
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
