"use client";

import { useCallback, useEffect, useState } from "react";
import { Capability, getCapabilities } from "./capabilities.api";

export function useCapabilities() {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setCapabilities(await getCapabilities());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Capability status is unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh(); }, 0);
    return () => window.clearTimeout(timer);
  }, [refresh]);
  return { capabilities, error, loading, refresh };
}
