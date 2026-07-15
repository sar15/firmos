"use client";
import { useEffect, useState } from "react";
import { getAuthHeaders } from "@/lib/auth";

type Sync = { id: string; capability_key: string; status: string; completeness: string; processed_count: number; mapping_blockers: string[] };
type Installation = { id: string; provider: string; display_name: string; status: string; configuration?: { organization_name?: string; gstin_warning?: string }; credential_healthy: boolean; token_expires_at?: string; data_center?: string; scopes: string[]; worker_healthy: boolean; capabilities: { key: string; state: string; reason?: string }[]; certifications: { capability_key: string; level: number; provider_version: string }[]; mapping_count: number; partial_syncs: number; pending_writes: number; failed_writes: number; verification_mismatches: number; last_complete_sync?: string; recent_syncs: Sync[]; mismatch_details: { mismatches: Record<string, unknown> }[] };

export function ConnectorOperations() {
  const [items, setItems] = useState<Installation[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const load = () => getAuthHeaders().then(headers => fetch("/api/connector-operations", { headers, cache: "no-store" }))
    .then(response => response.ok ? response.json() : Promise.reject()).then(body => setItems(body.installations));
  useEffect(() => { load().catch(() => setItems([])); }, []);
  const retry = async (sync: Sync) => {
    setBusy(sync.id); setNotice("");
    try {
      const response = await fetch(`/api/connector-operations/sync-jobs/${sync.id}/retry`, { method: "POST", headers: await getAuthHeaders() });
      if (!response.ok) throw new Error();
      await load(); setNotice("Read sync queued from its saved cursor.");
    } catch { setNotice("This sync cannot be resumed. Review its status and try again."); }
    finally { setBusy(null); }
  };
  if (!items.length) return null;
  return <section className="mb-6 space-y-3" aria-label="Connector operations">
    <h2 className="text-sm font-semibold text-[var(--text)]">Operations</h2>
    {notice && <p aria-live="polite" className="rounded-md border border-[var(--hairline)] bg-[var(--hover)] px-3 py-2 text-sm text-[var(--text)]">{notice}</p>}
    {items.map(item => <article key={item.id} className="rounded-lg border border-[var(--hairline)] bg-white p-4">
      <div className="flex items-center justify-between"><div><p className="text-sm font-medium text-[var(--text)]">{item.display_name}</p><p className="text-xs text-[var(--muted)]">{item.provider} · {item.status} · Credentials {item.credential_healthy ? "healthy" : "need attention"} · Worker {item.worker_healthy ? "online" : "offline"}</p></div><span className="text-xs text-[var(--muted)]">{item.last_complete_sync ? `Last complete sync ${new Date(item.last_complete_sync).toLocaleString()}` : "No complete sync"}</span></div>
      <p className="mt-2 text-xs text-[var(--muted)]">Organization {item.configuration?.organization_name ?? "not selected"} · Data center {item.data_center ?? "unknown"} · Token {item.token_expires_at ? `refreshes after ${new Date(item.token_expires_at).toLocaleString()}` : "expiry unavailable"}</p>
      {item.configuration?.gstin_warning && <p className="mt-2 text-xs text-amber-700">The Zoho organization GSTIN differs from the selected FirmOS client.</p>}
      <p className="mt-2 break-words text-[11px] text-[var(--muted)]">Scopes: {item.scopes?.join(", ") || "none reported"}</p>
      <div className="mt-3 flex flex-wrap gap-1">{item.capabilities.map(capability => <span key={capability.key} title={capability.reason} className="rounded border border-[var(--hairline)] px-2 py-1 text-[11px] text-[var(--muted)]">{capability.key}: {capability.state}</span>)}</div>
      <p className="mt-3 text-xs text-[var(--muted)]">Certification: {item.certifications?.length ? item.certifications.map(certification => `${certification.capability_key} L${certification.level} (${certification.provider_version})`).join(" · ") : "L0 — implementation only"}</p>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">{[["Mappings", item.mapping_count], ["Partial syncs", item.partial_syncs], ["Pending writes", item.pending_writes], ["Failed writes", item.failed_writes], ["Mismatches", item.verification_mismatches]].map(([label, value]) => <div key={label as string} className="rounded bg-[var(--hover)] p-2"><dt className="text-[var(--muted)]">{label}</dt><dd className="mt-1 font-semibold text-[var(--text)]">{value}</dd></div>)}</dl>
      {!!item.recent_syncs?.length && <p className="mt-3 text-xs text-[var(--muted)]">Recent sync: {item.recent_syncs.map(sync => `${sync.capability_key.replace("zoho.sync.", "")}: ${sync.status}/${sync.completeness} (${sync.processed_count})`).join(" · ")}</p>}
      <div className="mt-3 flex flex-wrap gap-2">{item.recent_syncs.filter(sync => sync.status === "FAILED").map(sync => <button key={sync.id} type="button" disabled={busy === sync.id} onClick={() => retry(sync)} className="min-h-11 cursor-pointer rounded-md border border-[var(--hairline)] bg-white px-3 text-sm font-medium text-[var(--text)] transition-colors hover:bg-[var(--hover)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-wait disabled:opacity-50">{busy === sync.id ? "Queuing…" : `Resume ${sync.capability_key.replace("zoho.sync.", "")}`}</button>)}</div>
      <button type="button" disabled title="Available after controlled sandbox certification" className="mt-3 cursor-not-allowed rounded border border-[var(--hairline)] px-3 py-1.5 text-xs text-[var(--muted)] opacity-60">Sandbox purchase-bill test</button>
      {(!item.credential_healthy || !item.worker_healthy || item.failed_writes > 0 || item.verification_mismatches > 0) && <p className="mt-3 text-xs text-amber-700">Recovery: restore credentials and worker health, then review failed writes and verification mismatches before retrying.</p>}
    </article>)}
  </section>;
}
