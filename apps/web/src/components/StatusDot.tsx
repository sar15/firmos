import { cn } from "@/lib/utils";

export type StatusDotColor = "royal" | "amber" | "red" | "slate";

interface StatusDotProps extends React.HTMLAttributes<HTMLDivElement> {
  color: StatusDotColor;
}

export function StatusDot({ color, className, title, ...props }: StatusDotProps) {
  const colorMap = {
    royal: "bg-[var(--royal)]",
    amber: "bg-[var(--amber)]",
    red: "bg-[var(--red)]",
    slate: "bg-slate-500",
  };

  return (
    <div 
      className={cn(`w-1.5 h-1.5 rounded-full ${colorMap[color]}`, className)} 
      title={title}
      {...props} 
    />
  );
}
