"use client";

import { useEffect, useState } from "react";

import { setSelectedFirmId } from "@/lib/auth";
import { FirmMembership, listFirms } from "./firms.api";

export const FirmSelector = () => {
  const [firms, setFirms] = useState<FirmMembership[]>([]);
  const [selectedFirmId, setSelected] = useState("");

  useEffect(() => {
    listFirms().then(({ currentFirmId, firms: memberships }) => {
      const stored = window.localStorage.getItem("firmos:selectedFirmId");
      const selected = memberships.some((firm) => firm.id === stored) ? stored! : currentFirmId;
      setSelectedFirmId(selected);
      setSelected(selected);
      setFirms(memberships);
    }).catch(() => setFirms([]));
  }, []);

  if (firms.length === 0) return null;
  if (firms.length === 1) {
    return <span className="max-w-40 truncate text-xs text-[var(--muted)]">{firms[0].name}</span>;
  }

  return (
    <label className="flex items-center gap-2 text-xs text-[var(--muted)]">
      <span className="sr-only">Current firm</span>
      <select
        className="h-9 max-w-52 rounded-[6px] border border-[var(--hairline)] bg-white px-3 text-[13px] text-[var(--text)]"
        value={selectedFirmId}
        onChange={(event) => {
          setSelectedFirmId(event.target.value);
          setSelected(event.target.value);
          window.location.reload();
        }}
      >
        {firms.map((firm) => <option key={firm.id} value={firm.id}>{firm.name}</option>)}
      </select>
    </label>
  );
};
