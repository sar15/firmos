"use client";

import React from "react";

export function ClientFocusCard() {
  return (
    <div className="bg-[var(--raised)] border border-[var(--hairline)] rounded-[6px] p-3.5 mb-5.5">
      <div className="flex items-center gap-2.5 mb-2.5">
        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#FF6B35] to-[#F59E0B] text-white flex items-center justify-center text-[13px] font-bold shrink-0 shadow-sm">
          A
        </div>
        <div>
          <div className="text-[14px] font-semibold leading-tight text-[var(--text)]">Acme Traders</div>
          <div className="text-[11px] text-[var(--muted)] font-mono mt-0.5">27AABCA…1Z5 · PROP</div>
        </div>
      </div>
      
      <div className="grid grid-cols-2 gap-2 mt-3">
        <div className="p-2.5 bg-[var(--inset)] rounded-[6px]">
          <div className="text-[10px] text-[var(--muted-2)] uppercase tracking-[0.06em] font-semibold">Status</div>
          <div className="font-mono text-[14px] font-semibold mt-1 text-[var(--amber)]">DUE SOON</div>
        </div>
        <div className="p-2.5 bg-[var(--inset)] rounded-[6px]">
          <div className="text-[10px] text-[var(--muted-2)] uppercase tracking-[0.06em] font-semibold">3B due</div>
          <div className="font-mono text-[14px] font-semibold mt-1 text-[var(--text)]">3 days</div>
        </div>
        <div className="p-2.5 bg-[var(--inset)] rounded-[6px]">
          <div className="text-[10px] text-[var(--muted-2)] uppercase tracking-[0.06em] font-semibold">YTD paid</div>
          <div className="font-mono text-[14px] font-semibold mt-1 text-[var(--text)]">₹4.82L</div>
        </div>
        <div className="p-2.5 bg-[var(--inset)] rounded-[6px]">
          <div className="text-[10px] text-[var(--muted-2)] uppercase tracking-[0.06em] font-semibold">Open ITC</div>
          <div className="font-mono text-[14px] font-semibold mt-1 text-[var(--amber)]">₹18.4k</div>
        </div>
      </div>
    </div>
  );
}
