"use client";

import React, { useState } from "react";
import { Check, AlertCircle, X, Loader2, ChevronDown } from "lucide-react";

export interface TimelineAuditEntry {
  id: string;
  action: string;
  description: string;
  time?: string;
  details?: string;
  status?: "done" | "warn" | "err" | "spin";
}

export function StepCard({ entry }: { entry: TimelineAuditEntry }) {
  const [expanded, setExpanded] = useState(false);

  const getIcon = () => {
    switch (entry.status) {
      case "done":
        return <div className="w-[18px] h-[18px] rounded-full flex items-center justify-center bg-[var(--royal)] text-white shrink-0 mt-px"><Check className="w-[10px] h-[10px]" strokeWidth={3} /></div>;
      case "warn":
        return <div className="w-[18px] h-[18px] rounded-full flex items-center justify-center bg-[var(--amber)] text-white shrink-0 mt-px"><AlertCircle className="w-[10px] h-[10px]" strokeWidth={3} /></div>;
      case "err":
        return <div className="w-[18px] h-[18px] rounded-full flex items-center justify-center bg-[var(--red)] text-white shrink-0 mt-px"><X className="w-[10px] h-[10px]" strokeWidth={3} /></div>;
      case "spin":
        return <div className="w-[18px] h-[18px] rounded-full flex items-center justify-center bg-[var(--royal)] text-white shrink-0 mt-px"><Loader2 className="w-[10px] h-[10px] animate-spin" strokeWidth={3} /></div>;
      default:
        return <div className="w-[18px] h-[18px] rounded-full flex items-center justify-center bg-[var(--royal)] text-white shrink-0 mt-px"><Check className="w-[10px] h-[10px]" strokeWidth={3} /></div>;
    }
  };

  return (
    <div className={`flex items-start gap-3 p-3 border-b border-[var(--hairline)] text-[13.5px] transition-colors hover:bg-[var(--hover)] ${expanded ? 'bg-[var(--hover)]' : ''} last:border-b-0`}>
      {getIcon()}
      <div className="flex-1 min-w-0">
        <div className="text-[var(--text)] font-medium leading-[1.4]">
          {entry.description}
          {entry.time && <span className="font-mono text-[12.5px] text-[var(--text-2)] ml-1">· {entry.time}</span>}
        </div>
        
        {entry.details && !expanded && (
          <button 
            onClick={() => setExpanded(true)}
            className="text-[var(--royal)] text-[12px] font-medium mt-1 inline-flex items-center gap-1 hover:underline focus:outline-none"
          >
            Show details <ChevronDown className="w-3 h-3" />
          </button>
        )}

        {expanded && entry.details && (
          <div className="mt-2 p-2.5 bg-[var(--inset)] rounded-[6px] border border-[var(--hairline)] font-mono text-[11.5px] text-[var(--text-2)] leading-relaxed whitespace-pre-wrap overflow-x-auto animate-in slide-in-from-top-1 fade-in duration-200">
            {entry.details}
            <button 
              onClick={() => setExpanded(false)}
              className="mt-2 text-[var(--royal)] hover:underline block"
            >
              Hide
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
