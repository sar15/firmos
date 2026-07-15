"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { PurchaseRegisterTable } from "@/features/registers/PurchaseRegisterTable";
import { getPurchaseRegister, getPurchaseRegisterStatus, RegisterStatus, syncZohoRegisters } from "@/features/registers/registers.api";
import { PurchaseRegisterRow } from "@/features/registers/registers.types";

export default function PurchaseRegisterPage() {
  const params = useParams();
  const clientId = params?.id as string;
  const [rows, setRows] = useState<PurchaseRegisterRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [freshness, setFreshness] = useState<RegisterStatus | null>(null);
  const [periodInput, setPeriodInput] = useState(() => new Date().toISOString().slice(0, 7));

  const registerPeriod = `${periodInput.slice(5, 7)}${periodInput.slice(0, 4)}`;
  const period = new Date(`${periodInput}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

  useEffect(() => {
    setLoading(true);
    Promise.all([getPurchaseRegister(clientId, registerPeriod), getPurchaseRegisterStatus(clientId, registerPeriod)])
      .then(([nextRows, status]) => { setRows(nextRows); setFreshness(status); })
      .catch((e) => console.error("Failed to load purchase register", e))
      .finally(() => setLoading(false));
  }, [clientId, registerPeriod]);

  const sync = async () => {
    setSyncing(true);
    try {
      await syncZohoRegisters(clientId, registerPeriod);
      setRows(await getPurchaseRegister(clientId, registerPeriod));
      setFreshness(await getPurchaseRegisterStatus(clientId, registerPeriod));
    } finally { setSyncing(false); }
  };

  return (
    <div className="flex-1 overflow-y-auto p-8 pt-6">
      <div className="max-w-[880px] mx-auto">
        <Link
          href={`/clients/${clientId}`}
          className="inline-flex items-center gap-1.5 text-[13px] text-[var(--muted)] hover:text-[var(--royal)] mb-4 transition-colors font-medium"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to client
        </Link>
        <div className="flex items-center gap-2 mb-4">
          <input aria-label="Register period" type="month" value={periodInput} onChange={(event) => setPeriodInput(event.target.value)} className="min-h-11 rounded border px-3" />
          <button onClick={sync} disabled={syncing} className="min-h-11 rounded bg-[var(--royal)] px-4 text-white disabled:opacity-50">{syncing ? "Syncing…" : "Sync Zoho"}</button>
        </div>
        {freshness && freshness.state !== "COMPLETE" && (
          <div role="status" className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
            Register is {freshness.state.toLowerCase()}. {freshness.message || "Counts or totals have not reconciled, so this period is not marked complete."}
          </div>
        )}

        {loading ? (
          <div className="py-20 text-center text-[var(--muted)]">Loading purchase register...</div>
        ) : rows.length === 0 ? (
          <div className="py-20 text-center">
            <div className="text-[var(--muted)] text-[15px]">No bills found for this period.</div>
            <div className="text-[var(--muted-2)] text-[13px] mt-2">Connect Zoho Books or upload vendor bills to populate.</div>
          </div>
        ) : (
          <PurchaseRegisterTable rows={rows} period={period} />
        )}
      </div>
    </div>
  );
}
