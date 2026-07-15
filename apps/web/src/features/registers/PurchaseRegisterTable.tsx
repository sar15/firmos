"use client";

import React from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PurchaseRegisterRow } from "./registers.types";

const formatPaise = (paise: number): string => {
  return `₹${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
};

interface PurchaseRegisterTableProps {
  rows: PurchaseRegisterRow[];
  period: string;
}

export const PurchaseRegisterTable = ({ rows, period }: PurchaseRegisterTableProps) => {
  const totalTax = rows.reduce((sum, r) => sum + r.taxTotalPaise, 0);
  const totalAmount = rows.reduce((sum, r) => sum + r.totalPaise, 0);
  const exportCsv = () => {
    const cells = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const lines = [["Supplier", "GSTIN", "Invoice", "Date", "Tax paise", "Total paise", "Source", "Verified"],
      ...rows.map(row => [row.vendorName, row.vendorGstin, row.billNumber, row.billDate,
        row.taxTotalPaise, row.totalPaise, row.source, row.verified])];
    const url = URL.createObjectURL(new Blob([lines.map(line => line.map(cells).join(",")).join("\n")], { type: "text/csv" }));
    const link = document.createElement("a");
    link.href = url; link.download = `purchase-register-${period}.csv`; link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-end justify-between mb-1.5 flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-[-0.025em] text-[var(--text)]">Purchase Register</h1>
          <div className="text-[var(--muted)] text-[13.5px] mt-1">
            {rows.length} bills · Period {period}
          </div>
        </div>
        <div className="flex gap-4">
          <Button variant="outline" onClick={exportCsv}>Export CSV</Button>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.06em] text-[var(--muted-2)] font-semibold">Total Purchases</div>
            <div className="font-mono text-[14px] font-semibold text-[var(--text)] mt-0.5">{formatPaise(totalAmount)}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase tracking-[0.06em] text-[var(--muted-2)] font-semibold">Input Tax (ITC)</div>
            <div className="font-mono text-[14px] font-semibold text-[var(--royal)] mt-0.5">{formatPaise(totalTax)}</div>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="mt-5 overflow-x-auto" role="region" aria-label="Verified purchase register" tabIndex={0}>
        <div className="min-w-[760px]">
        {/* Column headers */}
        <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-3 px-1 pb-2 border-b border-[var(--hairline)] text-[11px] uppercase tracking-[0.06em] text-[var(--muted-2)] font-semibold">
          <span>Vendor</span>
          <span className="text-right w-[90px]">Date</span>
          <span className="text-right w-[110px]">Total</span>
          <span className="text-right w-[110px]">Tax</span>
          <span className="text-center w-[60px]">Source</span>
          <span className="text-right w-[60px]">Status</span>
        </div>

        {/* Rows */}
        {rows.map((row) => (
          <div
            key={row.id}
            className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-3 px-1 py-3.5 border-b border-[var(--hairline)] items-center cursor-default hover:bg-[var(--hover)] rounded-[6px] -mx-1 px-2 transition-colors"
          >
            <div>
              {row.documentId ? (
                <Link href={`/documents/${row.documentId}`} className="text-[14.5px] font-medium text-[var(--text)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]">
                  {row.vendorName}
                </Link>
              ) : <div className="text-[14.5px] font-medium text-[var(--text)]">{row.vendorName}</div>}
              <div className="text-[11.5px] text-[var(--muted)] mt-0.5">
                <span className="font-mono">{row.billNumber}</span>
                {row.vendorGstin && <span className="ml-2 font-mono text-[10.5px] text-[var(--muted-2)]">{row.vendorGstin}</span>}
              </div>
            </div>
            <span className="font-mono text-[13px] text-[var(--muted)] text-right w-[90px] tabular-nums">{row.billDate}</span>
            <span className="font-mono text-[13.5px] text-[var(--text-2)] font-medium text-right w-[110px] tabular-nums">{formatPaise(row.totalPaise)}</span>
            <span className="font-mono text-[13.5px] text-[var(--text-2)] font-medium text-right w-[110px] tabular-nums">{formatPaise(row.taxTotalPaise)}</span>
            <span className="text-center w-[60px]">
              <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                row.source.startsWith("ZOHO") ? "bg-[var(--royal-tint)] text-[var(--royal)]" :
                "bg-[var(--amber-tint)] text-[var(--amber)]"
              }`}>{row.source.startsWith("ZOHO") ? "Zoho" : row.source === "TALLY_PRIME" ? "Tally" : "Manual"}</span>
            </span>
            <span className="text-right w-[60px]">
              <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${
                row.verified ? "bg-emerald-50 text-emerald-700" :
                "bg-[var(--amber-tint)] text-[var(--amber)]"
              }`}>{row.verified ? "Verified" : row.status}</span>
            </span>
          </div>
        ))}
      {/* Totals */}
      <div className="grid grid-cols-[1fr_auto_auto_auto_auto_auto] gap-3 px-2 py-3 mt-1 border-t-2 border-[var(--hairline-2)]">
        <span className="text-[14px] font-semibold text-[var(--text)]">Total</span>
        <span className="w-[90px]" />
        <span className="font-mono text-[14px] font-semibold text-[var(--text)] text-right w-[110px] tabular-nums">{formatPaise(totalAmount)}</span>
        <span className="font-mono text-[14px] font-semibold text-[var(--royal)] text-right w-[110px] tabular-nums">{formatPaise(totalTax)}</span>
        <span className="w-[60px]" />
        <span className="w-[60px]" />
      </div>
        </div>
      </div>
    </div>
  );
};
