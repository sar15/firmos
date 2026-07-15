"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, FileCheck2, RefreshCw, ShieldAlert } from "lucide-react";
import { activateItrRule, approveItr, authorizeItr, createItr, draftItr, getItr, ItrReconciliation, ItrWorkspace as Workspace, packItr, reconcileItr } from "./workpapers.api";
import { ItrSourceForm } from "./ItrSourceForm";

type WorkspaceView = { workspace: Workspace; sources: { source_type: string; source_version: string }[]; reconciliation: ItrReconciliation[]; authorizations: { authorized_by: string; evidence_reference: string }[] };

export function ItrWorkspace({ clientId }: { clientId: string }) {
  const year = new Date().getFullYear();
  const [assessmentYear, setAssessmentYear] = useState(`${year}-${String(year + 1).slice(-2)}`);
  const [taxpayerName, setTaxpayerName] = useState("");
  const [pan, setPan] = useState("");
  const [evidence, setEvidence] = useState("");
  const [view, setView] = useState<WorkspaceView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [regime,setRegime]=useState<"NEW"|"OLD">("NEW");

  const load = useCallback(async () => {
    try { setView(await getItr(clientId, assessmentYear)); }
    catch { setView(null); }
  }, [assessmentYear, clientId]);
  useEffect(() => { void load(); }, [load]);

  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await action(); await load(); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "The workspace could not be updated."); }
    finally { setBusy(false); }
  };
  const create = () => run(async () => {
    const workspace = await createItr(clientId, assessmentYear, pan.trim().toUpperCase(), taxpayerName.trim());
    await authorizeItr(workspace.id, taxpayerName.trim(), evidence.trim());
  });
  const workspace = view?.workspace;
  const reconciled=Boolean(view?.reconciliation.length&&view.reconciliation.every(item=>item.status==="MATCHED"));
  const computed=Boolean(workspace&&Object.keys(workspace.computation||{}).length);
  const action = workspace?.status === "NEEDS_REVIEW" && computed ? () => run(() => approveItr(workspace.id))
    : workspace?.status === "NEEDS_REVIEW" && reconciled ? () => run(() => draftItr(workspace.id,regime))
    : workspace?.status === "APPROVED" ? () => run(() => packItr(workspace.id))
    : workspace && view.sources.length ? () => run(() => reconcileItr(workspace.id)) : undefined;
  const actionLabel = workspace?.status === "NEEDS_REVIEW" && computed ? "Approve computation"
    : workspace?.status === "NEEDS_REVIEW" ? "Draft schedules and tax"
    : workspace?.status === "APPROVED" ? "Generate manual pack" : "Reconcile sources";

  return <div>
    <label className="text-xs font-medium text-[var(--muted)]">Assessment year
      <input value={assessmentYear} onChange={event => setAssessmentYear(event.target.value)} pattern="[0-9]{4}-[0-9]{2}" className="mt-1 block min-h-11 w-36 rounded-md border bg-white px-3 text-sm" />
    </label>
    {!workspace ? <section className="mt-6 rounded-xl border bg-white p-5 sm:p-6">
      <p className="text-xs font-semibold uppercase tracking-[.1em] text-[var(--muted)]">Authorization record</p>
      <h2 className="mt-2 text-xl font-semibold">Start with taxpayer consent</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--muted)]">The workspace stays locked until the taxpayer identity and authorization evidence are recorded.</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="text-xs font-medium text-[var(--muted)]">Taxpayer name<input value={taxpayerName} onChange={event => setTaxpayerName(event.target.value)} className="mt-1 block min-h-11 w-full rounded-md border px-3 text-sm" /></label>
        <label className="text-xs font-medium text-[var(--muted)]">PAN<input value={pan} onChange={event => setPan(event.target.value.toUpperCase())} maxLength={10} className="mt-1 block min-h-11 w-full rounded-md border px-3 font-mono text-sm uppercase" /></label>
        <label className="text-xs font-medium text-[var(--muted)] sm:col-span-2">Consent evidence reference<input value={evidence} onChange={event => setEvidence(event.target.value)} placeholder="Signed engagement or consent record" className="mt-1 block min-h-11 w-full rounded-md border px-3 text-sm" /></label>
      </div>
      <button disabled={busy || taxpayerName.trim().length < 2 || !/^[A-Z]{5}[0-9]{4}[A-Z]$/.test(pan) || !evidence.trim()} onClick={create} className="btn-primary mt-5 inline-flex min-h-11 items-center gap-2 rounded-md px-4 text-sm disabled:opacity-50">
        {busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}Create authorized workspace
      </button>
    </section> : <section className="mt-6 rounded-xl border bg-white p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[.1em] text-[var(--muted)]">{workspace.taxpayer_pan}</p><h2 className="mt-2 text-xl font-semibold">{workspace.taxpayer_name}</h2><p className="mt-1 text-sm text-[var(--muted)]">{workspace.status.replaceAll("_", " ")}</p></div>
        {workspace.stale && <span className="inline-flex items-center gap-1 text-xs text-amber-800"><ShieldAlert className="h-4 w-4" />Sources changed</span>}
      </div>
      <div className="mt-6 grid gap-px overflow-hidden rounded-lg border bg-[var(--hairline)] sm:grid-cols-3">
        {[["Authorization", view.authorizations.length ? "Recorded" : "Required"], ["Evidence sources", String(view.sources.length)], ["Reconciliation", view.reconciliation.length ? `${view.reconciliation.filter(item => item.status === "MATCHED").length}/${view.reconciliation.length} matched` : "Not run"]].map(([label, value]) => <div key={label} className="bg-[var(--panel)] p-4"><p className="text-xs text-[var(--muted)]">{label}</p><p className="mt-2 text-sm font-semibold">{value}</p></div>)}
      </div>
      {!view.sources.length && <p className="mt-5 text-sm leading-6 text-[var(--muted)]">Add classified AIS, 26AS, books and supporting evidence before reconciliation. Source identity and versions are checked against this PAN and AY.</p>}
      <ItrSourceForm workspaceId={workspace.id} clientId={clientId} clientName={workspace.taxpayer_name} pan={workspace.taxpayer_pan} onSaved={load}/>
      {reconciled&&!computed&&<div className="mt-5 flex flex-wrap items-end gap-3"><label className="text-xs text-[var(--muted)]">Tax regime<select value={regime} onChange={event=>setRegime(event.target.value as "NEW"|"OLD")} className="mt-1 block h-11 rounded-md border bg-white px-3 text-sm"><option>NEW</option><option>OLD</option></select></label><button disabled={busy} onClick={()=>run(()=>activateItrRule(assessmentYear))} className="min-h-11 rounded-md border px-4 text-sm font-medium disabled:opacity-50">Review and activate AY rules</button></div>}
      {action && <button disabled={busy} onClick={action} className="btn-primary mt-5 inline-flex min-h-11 items-center gap-2 rounded-md px-4 text-sm disabled:opacity-50">{busy ? <RefreshCw className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}{actionLabel}</button>}
    </section>}
    {error && <p role="alert" className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</p>}
    <p className="mt-5 text-xs leading-5 text-[var(--muted)]">firmOS prepares a manual filing pack only. External filing, payment, e-verification and acknowledgement remain separately evidenced events.</p>
  </div>;
}
