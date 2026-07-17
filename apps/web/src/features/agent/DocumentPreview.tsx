"use client";

import React from "react";
import { Camera } from "lucide-react";

export function DocumentPreview() {
  return (
    <div className="mt-3.5 bg-[var(--raised)] border border-[var(--hairline)] rounded-[6px] overflow-hidden">
      <div className="relative flex h-[130px] items-center justify-center overflow-hidden bg-[var(--inset)]">
        <div className="absolute inset-0 opacity-10 bg-[url('data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI4IiBoZWlnaHQ9IjgiPgo8cmVjdCB3aWR0aD0iOCIgaGVpZ2h0PSI4IiBmaWxsPSIjZmZmIj48L3JlY3Q+CjxwYXRoIGQ9Ik0wIDBMOCA4Wk04IDBMMCA4WiIgc3Ryb2tlPSIjMDAwIiBzdHJva2Utd2lkdGg9IjEiPjwvcGF0aD4KPC9zdmc+')] mix-blend-overlay"></div>
        <div className="relative bg-white/95 dark:bg-slate-900/95 text-slate-900 dark:text-slate-100 px-3.5 py-2 rounded-[6px] text-[12px] font-medium flex items-center gap-2">
          <Camera className="w-3.5 h-3.5" />
          <span>Invoice · Shree Traders</span>
        </div>
      </div>
      <div className="p-4 px-5">
        <div className="flex justify-between items-baseline py-1.5 text-[13.5px] border-b border-[var(--hairline)]">
          <span className="text-[var(--muted)]">Vendor</span>
          <span className="font-medium text-[var(--text)]">Shree Traders</span>
        </div>
        <div className="flex justify-between items-baseline py-1.5 text-[13.5px] border-b border-[var(--hairline)]">
          <span className="text-[var(--muted)]">Invoice</span>
          <span className="font-medium font-mono text-[var(--text)]">INV-2026-088</span>
        </div>
        <div className="flex justify-between items-baseline py-1.5 text-[13.5px] border-b border-[var(--hairline)]">
          <span className="text-[var(--muted)]">Taxable</span>
          <span className="font-medium font-mono text-[var(--text)]">₹15,637.50</span>
        </div>
        <div className="flex justify-between items-baseline py-1.5 text-[13.5px] border-b border-[var(--hairline-2)]">
          <span className="text-[var(--muted)]">CGST + SGST 18%</span>
          <span className="font-medium font-mono text-[var(--text)]">₹2,812.50</span>
        </div>
        <div className="flex justify-between items-baseline pt-2.5 mt-1 text-[13.5px]">
          <span className="font-semibold text-[var(--text)]">Total</span>
          <span className="font-semibold text-[15.5px] font-mono text-[var(--text)]">₹18,450.00</span>
        </div>
        
        <div className="flex items-center gap-2 mt-3 p-2 bg-[var(--royal-tint)] border border-[var(--royal-tint-2)] rounded-[6px] text-[11.5px] text-[var(--royal)] font-medium">
          ✓ GSTIN valid · math checks · 0.96 confidence
        </div>
      </div>
    </div>
  );
}
