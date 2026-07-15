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
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "8px 12px",
        borderBottom: "1px solid var(--hairline, rgba(0,0,0,0.06))",
        fontFamily: "monospace",
        fontSize: "13px",
      }}
    >
      <span style={{ color: "#4B5563" }}>{label}</span>
      <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
        <span style={{ fontWeight: 600, color: "#111827" }}>₹{valueRupees}</span>
        <button
          onClick={handleCopy}
          style={{
            background: "transparent",
            border: "1px solid var(--hairline, rgba(0,0,0,0.12))",
            borderRadius: "4px",
            padding: "2px 6px",
            fontSize: "11px",
            color: copied ? "var(--royal, #2540D9)" : "#6B7280",
            cursor: "pointer",
          }}
        >
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    </div>
  );
}
