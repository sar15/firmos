"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { ClientHeader } from "@/features/clients/components/ClientHeader";
import { ComplianceCalendar } from "@/features/clients/components/ComplianceCalendar";
import { ActiveWorkflows } from "@/features/clients/components/ActiveWorkflows";
import { FilingHistory } from "@/features/clients/components/FilingHistory";
import { getClientProfile, ClientProfile } from "@/features/clients/clients.api";

export default function ClientProfilePage() {
  const params = useParams();
  const id = params?.id as string;
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    if (id) {
      getClientProfile(id)
        .then(setProfile)
        .catch(e => console.error("Failed to load client profile", e))
        .finally(() => setIsLoading(false));
    }
  }, [id]);

  if (isLoading) {
    return <div className="p-10 text-center text-muted">Loading client profile...</div>;
  }

  if (!profile) {
    return <div className="p-10 text-center text-red-600">Failed to load client profile.</div>;
  }

  return (
    <div className="w-full h-full flex justify-center p-8 pt-10 overflow-y-auto bg-white">
      <div className="w-full max-w-[860px] flex flex-col items-start">
        <ClientHeader client={profile.client} />
        <div className="w-full flex flex-col gap-10">
          <ComplianceCalendar />
          <ActiveWorkflows decisions={profile.recentDecisions} />
          <FilingHistory />
        </div>
      </div>
    </div>
  );
}
