"use client";

import React from "react";
import { AlertCircle } from "lucide-react";

interface ManualFilingCardProps {
  period: string;
}

export function ManualFilingCard({ period }: ManualFilingCardProps) {
  return (
    <div className="mt-3.5">
      <div className="text-[15.5px] font-medium text-[var(--royal)] flex items-center gap-2 mb-2">
        <div className="w-5 h-5 rounded-full bg-[var(--royal)] text-white flex items-center justify-center text-[11px] shrink-0">
          <AlertCircle className="w-3 h-3" strokeWidth={3} />
        </div>
        Manual portal filing required
      </div>
      <div className="text-[12.5px] text-[var(--muted)] font-mono">
        {period} · firmOS can prepare the pack but cannot claim submission without acknowledgement evidence.
      </div>
    </div>
  );
}
