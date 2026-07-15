import React from "react";

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="flex flex-col h-full bg-[var(--canvas)] animate-pulse">
      {/* Header skeleton */}
      <div className="h-[64px] border-b border-[var(--hairline)] px-6 flex flex-col justify-center gap-2">
        <div className="h-5 w-48 bg-[var(--hover)] rounded"></div>
        <div className="h-3 w-32 bg-[var(--hover)] rounded"></div>
      </div>
      
      {/* Filters/Toolbar skeleton */}
      <div className="h-[52px] border-b border-[var(--hairline)] px-6 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="h-7 w-24 bg-[var(--hover)] rounded-[6px]"></div>
          <div className="h-7 w-24 bg-[var(--hover)] rounded-[6px]"></div>
        </div>
        <div className="h-7 w-64 bg-[var(--hover)] rounded-[6px]"></div>
      </div>

      {/* Rows skeleton */}
      <div className="flex-1 flex flex-col">
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center border-b border-[var(--hairline)] h-[44px] px-6 gap-6">
            <div className="h-3 w-1/4 bg-[var(--hover)] rounded"></div>
            <div className="h-3 w-1/4 bg-[var(--hover)] rounded"></div>
            <div className="h-3 w-1/4 bg-[var(--hover)] rounded"></div>
            <div className="h-3 w-1/4 bg-[var(--hover)] rounded"></div>
          </div>
        ))}
      </div>
    </div>
  );
}
