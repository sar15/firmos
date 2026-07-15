import { AlertTriangle, CheckCircle2, PlugZap } from "lucide-react";
import { ReviewWorkspace } from "../documents.api";

type Provider = "ZOHO_BOOKS" | "TALLY_PRIME";

export function ReviewSidebar({ workspace, provider, onProviderChange }: {
  workspace: ReviewWorkspace | null;
  provider: Provider;
  onProviderChange: (provider: Provider) => void;
}) {
  const connected = new Set((workspace?.connectors || []).filter(item => item.status === "AVAILABLE").map(item => item.provider));
  const findings = workspace?.findings || [];
  const draft = workspace?.drafts.find(item => item.provider === provider);

  return (
    <aside className="flex h-full flex-col overflow-y-auto bg-[var(--panel)]" aria-label="Validation and posting review">
      <div className="border-b border-[var(--hairline)] p-5">
        <h2 className="text-base font-semibold text-[var(--text)]">Post & verify</h2>
        <p className="mt-1 text-sm leading-5 text-[var(--muted)]">Choose where this purchase should be created. Nothing is posted until approval.</p>
        <label className="mt-4 block text-xs font-semibold text-[var(--text-2)]" htmlFor="books-provider">Books connector</label>
        <select id="books-provider" value={provider} onChange={event => onProviderChange(event.target.value as Provider)}
          className="mt-2 min-h-11 w-full rounded-md border border-[var(--hairline)] bg-white px-3 text-sm text-[var(--text)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)]">
          <option value="ZOHO_BOOKS">Zoho Books{connected.has("ZOHO_BOOKS") ? " · connected" : " · not connected"}</option>
          <option value="TALLY_PRIME">Tally Prime{connected.has("TALLY_PRIME") ? " · connected" : " · not connected"}</option>
        </select>
        {!connected.has(provider) && (
          <p className="mt-2 flex gap-2 text-xs leading-5 text-[var(--amber)]"><PlugZap className="mt-0.5 h-4 w-4 shrink-0" />Connect this client before preparing the action.</p>
        )}
      </div>

      <div className="border-b border-[var(--hairline)] p-5">
        <h3 className="text-sm font-semibold text-[var(--text)]">Deterministic checks</h3>
        {findings.length === 0 ? (
          <p className="mt-3 flex gap-2 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" />No validation exceptions.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {findings.map(item => (
              <li key={`${item.code}-${item.field_key || "document"}`} className="flex gap-2 text-sm leading-5 text-[var(--text-2)]">
                <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${item.severity === "ERROR" ? "text-[var(--red)]" : "text-[var(--amber)]"}`} />
                <span><span className="font-medium">{item.code.replaceAll("_", " ")}</span><br /><span className="text-xs text-[var(--muted)]">{item.message}</span></span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="p-5">
        <h3 className="text-sm font-semibold text-[var(--text)]">Posting draft</h3>
        <dl className="mt-3 grid grid-cols-2 gap-3 text-xs">
          <dt className="text-[var(--muted)]">State</dt><dd className="text-right font-medium text-[var(--text)]">{draft?.status || "Not prepared"}</dd>
          <dt className="text-[var(--muted)]">Version</dt><dd className="text-right font-mono text-[var(--text)]">{draft?.version || "—"}</dd>
          <dt className="text-[var(--muted)]">Validation</dt><dd className="text-right font-medium text-[var(--text)]">{draft?.validation_state || "Pending"}</dd>
        </dl>
      </div>
    </aside>
  );
}
