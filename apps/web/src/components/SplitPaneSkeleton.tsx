import React from "react";

export function SplitPaneSkeleton() {
  return (
    <div className="flex h-full w-full animate-pulse bg-[var(--canvas)] flex-col md:flex-row">
      <div className="w-full md:w-[320px] lg:w-[400px] border-r border-[var(--hairline)] flex flex-col shrink-0">
        <div className="h-[64px] border-b border-[var(--hairline)] px-4 flex items-center">
          <div className="h-5 w-32 bg-[var(--hover)] rounded"></div>
        </div>
        <div className="flex-1 flex flex-col">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="flex flex-col border-b border-[var(--hairline)] p-4 gap-2">
              <div className="h-4 w-3/4 bg-[var(--hover)] rounded"></div>
              <div className="h-3 w-1/2 bg-[var(--hover)] rounded"></div>
            </div>
          ))}
        </div>
      </div>
      <div className="flex-1 flex flex-col bg-white">
        <div className="h-[64px] border-b border-[var(--hairline)] px-8 flex items-center">
          <div className="h-5 w-48 bg-[var(--hover)] rounded"></div>
        </div>
        <div className="p-8 flex flex-col gap-6">
          <div className="h-32 w-full max-w-2xl bg-[var(--hover)] rounded-[6px]"></div>
          <div className="h-32 w-full max-w-2xl bg-[var(--hover)] rounded-[6px]"></div>
        </div>
      </div>
    </div>
  );
}
