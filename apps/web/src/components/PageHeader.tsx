import React from "react";

interface PageHeaderProps {
  title: string;
  meta?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  contentClassName?: string;
}

export function PageHeader({ title, meta, children, className = "p-4 bg-[var(--canvas)]", contentClassName = "" }: PageHeaderProps) {
  return (
    <div className={`border-b border-[var(--hairline)] flex flex-col gap-4 sticky top-0 z-10 w-full ${className}`}>
      <div className={`w-full flex flex-col gap-4 ${contentClassName}`}>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-[var(--text)] leading-none">{title}</h2>
          {meta && (
            <div className="flex items-center gap-4">
              {meta}
            </div>
          )}
        </div>
        {children && (
          <div className="flex items-center gap-3 text-sm">
            {children}
          </div>
        )}
      </div>
    </div>
  );
}
