"use client";

import React, { useEffect, useState } from "react";
import { fetchManualGstPack, ManualGstPackResponse } from "./compliance.api";
import { formatIndianRupee } from "@/lib/formatIndianRupee";

interface Gstr3bTablesProps {
  clientId: string;
  period: string;
}

export function Gstr3bTables({ clientId, period }: Gstr3bTablesProps) {
  const [data, setData] = useState<ManualGstPackResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setData(null);
    setError(null);
    fetchManualGstPack(clientId, period)
      .then((pack) => active && setData(pack))
      .catch((err) => active && setError(err instanceof Error ? err.message : "Could not load the GST working pack"));
    return () => { active = false; };
  }, [clientId, period]);

  if (error) return <div className="p-4 text-sm text-[var(--red)]">{error}</div>;
  if (!data) return <div className="p-4 text-sm text-[var(--muted)]">Preparing manual GST working pack…</div>;

  const mismatch = data.gstr2b_mismatch_report.summary;
  return (
    <section className="space-y-4" aria-label="Manual GST filing pack">
      <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950">
        <p className="font-semibold">Manual portal filing required</p>
        <p className="mt-1 text-sm">This pack prepares the evidence and exceptions. firmOS does not submit on the GST portal.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <Metric label="Sales tax" value={formatIndianRupee(data.sales_register.tax_paise)} detail={`${data.sales_register.count} invoices`} />
        <Metric label="Matched ITC" value={formatIndianRupee(data.gstr3b_working.matched_itc_paise)} detail={`${mismatch.autoMatched} matched`} />
        <Metric label="Exceptions" value={String(mismatch.suggested + mismatch.unmatched)} detail={`${mismatch.suggested} suggested · ${mismatch.unmatched} unmatched`} />
      </div>
      <div className="rounded-lg border border-[var(--hairline)] bg-white p-4">
        <h3 className="font-semibold text-[var(--text)]">CA review checklist</h3>
        <ul className="mt-3 space-y-2 text-sm text-[var(--muted)]">
          {data.review_checklist.map((item) => <li key={item.item}>{item.complete ? "✓" : "○"} {item.item}</li>)}
        </ul>
        <p className="mt-4 text-xs text-[var(--muted)]">{data.gstr3b_working.warning}</p>
      </div>
    </section>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="rounded-lg border border-[var(--hairline)] bg-white p-4"><p className="text-sm text-[var(--muted)]">{label}</p><p className="mt-1 text-xl font-semibold text-[var(--text)]">{value}</p><p className="mt-1 text-xs text-[var(--muted)]">{detail}</p></div>;
}
