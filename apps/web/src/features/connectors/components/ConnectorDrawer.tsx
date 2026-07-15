import { Check, Copy, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getAuthHeaders } from "@/lib/auth";

interface ConnectorDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  connectorId: string | null;
  connectorName: string | null;
  description: string;
}

export function ConnectorDrawer({ isOpen, onClose, connectorId, connectorName, description }: ConnectorDrawerProps) {
  const [copied, setCopied] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clients, setClients] = useState<{ id: string; legalName: string }[]>([]);
  const [clientId, setClientId] = useState("");
  const [pairingCode, setPairingCode] = useState("");
  const tally = connectorId === "c5";
  useEffect(() => {
    if (!isOpen || !tally) return;
    void getAuthHeaders().then((headers) => fetch("/api/clients", { headers }))
      .then((res) => res.ok ? res.json() : Promise.reject(new Error("Clients could not be loaded")))
      .then((rows: { id: string; legalName: string }[]) => { setClients(rows); setClientId(rows[0]?.id || ""); })
      .catch((err) => setError(err instanceof Error ? err.message : "Clients could not be loaded"));
  }, [isOpen, tally]);
  if (!isOpen) return null;

  const zoho = connectorId === "c1";
  const manualGst = connectorId === "c2";

  const handleConnect = async () => {
    if ((!zoho && !tally) || !connectorId) return;
    setConnecting(true); setError(null);
    try {
      const res = await fetch(zoho ? `/api/connectors/${connectorId}/connect` : "/api/tally-agent/pairing-code", {
        method: "POST", headers: { ...await getAuthHeaders(), "Content-Type": "application/json" },
        body: tally ? JSON.stringify({ client_id: clientId }) : undefined,
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Connection failed.");
      if (zoho) window.location.assign(data.redirect_url); else setPairingCode(data.pairing_code);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed. Try again.");
    } finally { setConnecting(false); }
  };

  const copyPairingCode = async () => {
    await navigator.clipboard.writeText(pairingCode);
    setCopied(true); window.setTimeout(() => setCopied(false), 2000);
  };

  const title = zoho ? "Connect securely with Zoho" : tally ? "Connect the Tally Agent" : manualGst ? "Use manual GST evidence" : "Not available yet";
  const body = zoho ? "You will sign in to Zoho Books and approve the requested access there." : tally ? "The Windows agent talks to TallyPrime only on the office computer. A short-lived pairing code connects it without exposing Tally to the internet." : manualGst ? "Download GSTR-2B from the GST portal and upload the JSON in Reconciliation. firmOS prepares the review pack; filing remains manual." : "This integration is listed for the product roadmap, but it cannot be connected in this release.";

  return <>
    <button type="button" aria-label="Close connector details" className="fixed inset-0 z-40 cursor-default bg-slate-950/30 backdrop-blur-sm" onClick={onClose} />
    <aside role="dialog" aria-modal="true" aria-labelledby="connector-title" className="fixed right-0 top-0 z-50 flex h-dvh w-full max-w-[440px] flex-col border-l border-[var(--hairline)] bg-white shadow-2xl">
      <header className="flex items-start justify-between gap-4 border-b border-[var(--hairline)] p-5">
        <div><p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">Connector setup</p><h2 id="connector-title" className="mt-1 text-lg font-semibold text-[var(--text)]">{connectorName}</h2><p className="mt-1 text-sm text-[var(--muted)]">{description}</p></div>
        <button type="button" onClick={onClose} className="grid h-11 w-11 place-items-center rounded-md text-[var(--muted)] hover:bg-[var(--hover)] hover:text-[var(--text)]" aria-label="Close"><X className="h-5 w-5" /></button>
      </header>
      <div className="flex-1 space-y-6 overflow-y-auto p-5">
        <section><h3 className="font-semibold text-[var(--text)]">{title}</h3><p className="mt-2 text-sm leading-6 text-[var(--muted)]">{body}</p></section>
        {zoho && <section className="rounded-lg border border-[var(--hairline)] bg-[var(--hover)] p-4 text-sm text-[var(--muted)]"><p className="font-medium text-[var(--text)]">Requested access</p><ul className="mt-3 space-y-2"><li className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-[var(--royal)]" />Read sales, purchases, contacts, and accounts</li><li className="flex gap-2"><Check className="mt-0.5 h-4 w-4 text-[var(--royal)]" />Create an approved purchase bill</li></ul></section>}
        {tally && <section className="rounded-lg border border-[var(--hairline)] bg-[var(--hover)] p-4"><p className="text-sm font-medium text-[var(--text)]">Office setup</p><ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-6 text-[var(--muted)]"><li>Open the correct company in licensed TallyPrime.</li><li>Install and open the FirmOS Tally Agent on that Windows computer.</li><li>Choose the client below and generate a one-time code.</li></ol><label className="mt-4 block text-xs font-medium text-[var(--muted)]">FirmOS client<select value={clientId} onChange={(event) => setClientId(event.target.value)} className="mt-2 h-11 w-full rounded-md border border-[var(--hairline)] bg-white px-3 text-sm text-[var(--text)]">{clients.map((client) => <option key={client.id} value={client.id}>{client.legalName}</option>)}</select></label>{pairingCode && <div className="mt-4 flex items-center gap-2 rounded-md bg-slate-950 p-3"><code className="flex-1 break-all text-xs text-white">{pairingCode}</code><button type="button" onClick={copyPairingCode} className="grid h-9 w-9 shrink-0 place-items-center rounded text-white hover:bg-white/10" aria-label="Copy pairing code">{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}</button></div>}<p className="mt-2 text-xs text-[var(--muted)]">The code expires in 15 minutes and works once.</p></section>}
        {manualGst && <section className="rounded-lg border border-[var(--hairline)] bg-[var(--hover)] p-4 text-sm leading-6 text-[var(--muted)]">Start in <strong className="text-[var(--text)]">Reconciliation → GSTR-2B ↔ Purchases</strong>, select the return period, then upload the downloaded JSON.</section>}
      </div>
      <footer className="border-t border-[var(--hairline)] p-5"><p className="min-h-5 text-center text-sm text-[var(--red)]" role="alert">{error}</p>{zoho || (tally && !pairingCode) ? <button type="button" onClick={handleConnect} disabled={connecting || (tally && !clientId)} className="mt-3 h-11 w-full rounded-md bg-[var(--royal)] px-4 text-sm font-medium text-white hover:bg-[var(--royal-hover)] disabled:opacity-50">{connecting ? "Please wait…" : zoho ? "Continue to Zoho" : "Generate pairing code"}</button> : <button type="button" onClick={onClose} className="mt-3 h-11 w-full rounded-md border border-[var(--hairline)] text-sm font-medium text-[var(--text)] hover:bg-[var(--hover)]">Close</button>}</footer>
    </aside>
  </>;
}
