"use client";

import React, { useEffect, useState } from "react";
import { listAuditEntries } from "../audit.api";
import { AuditEntry } from "@/types";

export function AuditTable() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAuditEntries().then(setEntries).catch(() => setError("Audit entries could not be loaded. Try again after reconnecting."));
  }, []);

  if (error) return <div className="rounded-md border border-[var(--red-border)] bg-[var(--red-tint)] p-4 text-sm text-[var(--red)]">{error}</div>;
  if (!entries.length) return <div className="rounded-md border border-dashed border-[var(--hairline)] bg-white p-6 text-sm text-[var(--muted)]">No audit entries yet. Approved actions and evidence reviews will appear here.</div>;

  return <div className="w-full overflow-x-auto rounded-md border border-[var(--hairline)] bg-white">
    <table className="w-full min-w-[680px] text-left text-sm">
      <thead className="border-b border-[var(--hairline)] bg-[var(--hover)] text-xs uppercase tracking-wide text-[var(--muted)]">
        <tr><th className="px-4 py-3">Time</th><th className="px-4 py-3">Actor</th><th className="px-4 py-3">Action</th><th className="px-4 py-3">Description</th></tr>
      </thead>
      <tbody className="divide-y divide-[var(--hairline)]">
        {entries.map((entry) => <tr key={entry.id} className="hover:bg-[var(--hover)]">
          <td className="whitespace-nowrap px-4 py-3 font-mono text-xs text-[var(--muted)]">{new Date(entry.timestamp).toLocaleString()}</td>
          <td className="px-4 py-3 font-medium text-[var(--text)]">{entry.actorName}</td>
          <td className="px-4 py-3 font-mono text-xs text-[var(--muted)]">{entry.action}</td>
          <td className="px-4 py-3 text-[var(--text)]">{entry.description}</td>
        </tr>)}
      </tbody>
    </table>
  </div>;
}
