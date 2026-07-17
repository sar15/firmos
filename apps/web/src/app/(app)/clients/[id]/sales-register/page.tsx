"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ArrowLeft, RefreshCw, ShieldCheck, TriangleAlert } from "lucide-react";
import { SalesRegisterTable } from "@/features/registers/SalesRegisterTable";
import { getSalesRegister, getSalesRegisterStatus, RegisterStatus, syncZohoRegisters } from "@/features/registers/registers.api";
import { SalesRegisterRow } from "@/features/registers/registers.types";

export default function SalesRegisterPage() {
  const clientId = useParams()?.id as string;
  const [rows, setRows] = useState<SalesRegisterRow[]>([]);
  const [status, setStatus] = useState<RegisterStatus>({ state: "PARTIAL" });
  const [busy, setBusy] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState("");
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const periodCode = `${month.slice(5, 7)}${month.slice(0, 4)}`;
  const periodLabel = new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });

  const load = async () => {
    setBusy(true); setError("");
    try {
      const [data, freshness] = await Promise.all([
        getSalesRegister(clientId, periodCode), getSalesRegisterStatus(clientId, periodCode),
      ]);
      setRows(data); setStatus(freshness);
    } catch { setError("Sales data could not be loaded. Check the connector and try again."); }
    finally { setBusy(false); }
  };
  useEffect(() => { void load(); }, [clientId, periodCode]); // eslint-disable-line react-hooks/exhaustive-deps

  const sync = async () => {
    setSyncing(true); setError("");
    try { await syncZohoRegisters(clientId, periodCode); await load(); }
    catch { setError("The sync could not be queued. Confirm Zoho Books is connected for this client."); }
    finally { setSyncing(false); }
  };

  const complete = status.state === "COMPLETE";
  return (
    <main className="min-h-screen overflow-y-auto bg-[var(--canvas)] px-4 py-6 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <Link href={`/clients/${clientId}`} className="inline-flex min-h-11 items-center gap-2 text-sm font-medium text-[var(--muted)] hover:text-[var(--text)]">
          <ArrowLeft className="h-4 w-4" /> Client workspace
        </Link>
        <header className="mt-4 flex flex-col gap-5 border-b border-[var(--hairline)] pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--muted)]">Books · Revenue</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-[var(--text)]">Sales register</h1>
            <p className="mt-2 text-sm leading-6 text-[var(--muted)]">Verified customer invoices, GST treatment and source evidence in one reviewable register.</p>
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs font-medium text-[var(--muted)]">Return period
              <input aria-label="Return period" type="month" value={month} onChange={event => setMonth(event.target.value)}
                className="mt-1 block min-h-11 rounded-md border border-[var(--hairline)] bg-white px-3 text-sm text-[var(--text)] focus-visible:ring-2 focus-visible:ring-[var(--royal)]" />
            </label>
            <button onClick={sync} disabled={syncing} className="btn-primary inline-flex min-h-11 items-center gap-2 rounded-md px-4 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50">
              <RefreshCw className={`h-4 w-4 ${syncing ? "animate-spin" : ""}`} />{syncing ? "Queueing sync" : "Sync sales"}
            </button>
          </div>
        </header>

        <section className={`mt-5 flex items-start gap-3 rounded-[6px] border px-4 py-3 ${complete ? "border-[var(--royal-tint-2)] bg-[var(--royal-tint)]" : "border-[var(--amber-border)] bg-[var(--amber-tint)]"}`} aria-live="polite">
          {complete ? <ShieldCheck className="mt-0.5 h-5 w-5 text-[var(--royal)]" /> : <TriangleAlert className="mt-0.5 h-5 w-5 text-[var(--amber)]" />}
          <div><p className="text-sm font-medium text-[var(--text)]">{complete ? "Register is complete for this period" : "Completeness needs attention"}</p>
            <p className="mt-0.5 text-xs leading-5 text-[var(--muted)]">{status.message || (complete ? "Provider totals and row counts passed the latest sync." : "Sync the full provider period before using this register for GST workpapers.")}</p></div>
        </section>
        {error && <div role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{error}</div>}
        {busy ? <div className="py-24 text-center text-sm text-[var(--muted)]">Loading verified sales…</div> :
          rows.length ? <SalesRegisterTable rows={rows} period={periodLabel} /> :
          <div className="mt-8 rounded-xl border border-dashed border-[var(--hairline)] bg-white px-6 py-16 text-center">
            <h2 className="text-lg font-semibold text-[var(--text)]">No verified invoices yet</h2>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[var(--muted)]">Sync the period or upload a sales invoice. Drafts appear here only after provider read-back verification.</p>
          </div>}
      </div>
    </main>
  );
}
