"use client";

import { useState } from "react";
import { upload2BJson, ReconciliationResponse } from "./reconciliation.api";

export function useUpload2B(clientId: string, period: string) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ReconciliationResponse | null>(null);

  const uploadFile = async (file: File) => {
    setLoading(true);
    setError(null);

    try {
      if (!file.name.endsWith(".json")) {
        throw new Error("Only .json GSTR-2B portal files are supported in this upload path.");
      }

      const fileText = await file.text();
      const payload = JSON.parse(fileText);
      const res = await upload2BJson(clientId, period, payload);
      setData(res);
      return res;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to upload GSTR-2B file";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  };

  return { uploadFile, loading, error, data };
}
