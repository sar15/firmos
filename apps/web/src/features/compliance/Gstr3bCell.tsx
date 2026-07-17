"use client";

import React, { useState } from "react";

interface Gstr3bCellProps {
  label: string;
  paise?: number;
}

export function Gstr3bCell({ label, paise = 0 }: Gstr3bCellProps) {
  const [copied, setCopied] = useState(false);

  const valueRupees = (paise / 100).toFixed(2);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(valueRupees);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="flex items-center justify-between border-b border-[var(--hairline)] px-3 py-2 font-mono text-[13px]">
      <span className="text-[var(--muted)]">{label}</span>
      <div className="flex items-center gap-2">
        <span className="font-semibold text-[var(--text)]">₹{valueRupees}</span>
        <button
          onClick={handleCopy}
          className={`min-h-8 rounded-[6px] border border-[var(--hairline-2)] bg-transparent px-2 text-[11px] ${copied ? "text-[var(--royal)]" : "text-[var(--muted)]"}`}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
