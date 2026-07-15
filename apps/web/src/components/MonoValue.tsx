import { cn } from "@/lib/utils";

interface MonoValueProps extends React.HTMLAttributes<HTMLSpanElement> {
  children: React.ReactNode;
}

export function MonoValue({ children, className, ...props }: MonoValueProps) {
  return (
    <span 
      className={cn("text-[12px] text-muted font-mono tabular-nums text-right", className)}
      {...props}
    >
      {children}
    </span>
  );
}
