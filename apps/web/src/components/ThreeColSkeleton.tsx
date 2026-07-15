import React from "react";

export function ThreeColSkeleton() {
  return (
    <div className="flex flex-col h-full bg-[var(--canvas)] animate-pulse">
      <div className="h-[64px] border-b border-[var(--hairline)] bg-white px-6 flex items-center justify-between shrink-0">
        <div className="h-5 w-48 bg-[var(--hover)] rounded"></div>
        <div className="h-8 w-24 bg-[var(--hover)] rounded-[6px]"></div>
      </div>
      
      <div className="flex-1 overflow-hidden p-6 flex flex-col md:flex-row gap-6">
        <div className="flex-1 flex flex-col gap-2">
          <div className="h-10 w-full bg-[var(--hover)] rounded-[6px]"></div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={`col1-${i}`} className="h-12 w-full bg-white border border-[var(--hairline)] rounded-[6px]"></div>
          ))}
        </div>
        <div className="flex-1 flex flex-col gap-2">
          <div className="h-10 w-full bg-[var(--hover)] rounded-[6px]"></div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={`col2-${i}`} className="h-12 w-full bg-white border border-[var(--hairline)] rounded-[6px]"></div>
          ))}
        </div>
        <div className="w-full md:w-80 flex flex-col gap-2 shrink-0">
          <div className="h-10 w-full bg-[var(--hover)] rounded-[6px]"></div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={`col3-${i}`} className="h-12 w-full bg-white border border-[var(--hairline)] rounded-[6px]"></div>
          ))}
        </div>
      </div>
    </div>
  );
}
