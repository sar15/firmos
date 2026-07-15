"use client";

import React, { useEffect, useState } from "react";
import { getDecisions } from "@/features/decisions/decisions.api";
import { Decision } from "@/types";

export function NeedsYouList() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getDecisions()
      .then((data) => {
        setDecisions(data.slice(0, 5));
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to fetch decisions", err);
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="text-[13px] text-[var(--muted)]">Loading needs...</div>;

  return (
    <div className="mb-5.5">
      <div className="flex items-center gap-2 pb-2.5 border-b border-[var(--hairline)] mb-1.5">
        <span className="w-2 h-2 rounded-full bg-[var(--red)]"></span>
        <h3 className="text-[11px] uppercase tracking-[0.09em] text-[var(--muted)] font-semibold">Needs you</h3>
        <span className="font-mono text-[10.5px] text-[var(--muted-2)] ml-auto">{decisions.length}</span>
      </div>
      
      {decisions.length === 0 ? (
        <div className="text-[13px] text-[var(--muted)] mt-2">All caught up.</div>
      ) : (
        decisions.map((decision, idx) => (
          <div key={decision.id} className={`px-2 py-3 hover:bg-[var(--raised)] cursor-pointer rounded-[6px] -mx-2 transition-colors ${idx !== decisions.length - 1 ? 'border-b border-[var(--hairline)]' : ''}`}>
            <div className="flex justify-between items-baseline gap-2.5">
              <span className="text-[13.5px] font-medium leading-[1.4] text-[var(--text)] line-clamp-1">{decision.title}</span>
              <span className="font-mono tabular-nums text-[13px] font-medium shrink-0 text-[var(--text-2)]">
                {decision.confidence < 0.5 ? "Low Conf" : "Review"}
              </span>
            </div>
            <div className="text-[11.5px] text-[var(--muted)] mt-1 leading-[1.4]">
              {decision.clientId}
              <span className={`ml-1 font-mono text-[10px] px-1.5 py-0.5 rounded-full font-semibold ${decision.confidence < 0.5 ? 'bg-[var(--red-tint)] text-[var(--red)]' : 'bg-[var(--amber-tint)] text-[var(--amber)]'}`}>
                {decision.confidence < 0.5 ? "low conf" : "review"}
              </span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
