"use client";

import { ActiveWorkflows } from "./ActiveWorkflows";
import { ClientHeader } from "./ClientHeader";
import { ComplianceCalendar } from "./ComplianceCalendar";
import { FilingHistory } from "./FilingHistory";
import { useClientProfile } from "../useClientProfile";

export const ClientProfileWorkspace = ({ clientId }: { clientId: string }) => {
  const { profile, isLoading, error, reload } = useClientProfile(clientId);

  if (isLoading) {
    return <div className="p-10 text-center text-[var(--muted)]" role="status">Loading client profile…</div>;
  }

  if (error || !profile) {
    return (
      <div className="p-10 text-center" role="alert">
        <p className="text-sm text-[var(--red)]">{error || "Client details could not be loaded."}</p>
        <button type="button" onClick={() => void reload()} className="mt-4 min-h-11 rounded-[6px] bg-[var(--royal)] px-4 text-sm font-medium text-white hover:bg-[var(--royal-hover)]">
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full justify-center overflow-y-auto bg-white p-8 pt-10">
      <div className="flex w-full max-w-[860px] flex-col items-start">
        <ClientHeader client={profile.client} />
        <div className="flex w-full flex-col gap-10">
          <ComplianceCalendar />
          <ActiveWorkflows decisions={profile.recentDecisions} />
          <FilingHistory />
        </div>
      </div>
    </div>
  );
};
