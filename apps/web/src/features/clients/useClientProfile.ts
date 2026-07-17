"use client";

import { useCallback, useEffect, useState } from "react";
import { ClientProfile, getClientProfile } from "./clients.api";

export const useClientProfile = (clientId: string) => {
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!clientId) {
      setProfile(null);
      setError("The client could not be identified.");
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      setProfile(await getClientProfile(clientId));
    } catch {
      setProfile(null);
      setError("Client details could not be loaded. Check your connection and try again.");
    } finally {
      setIsLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { profile, isLoading, error, reload };
};
