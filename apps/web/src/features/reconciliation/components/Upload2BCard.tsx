"use client";

import React, { useState } from "react";
import { useUpload2B } from "../useUpload2B";

interface Upload2BCardProps {
  clientId: string;
  period: string;
  onSuccess?: () => void;
}

export function Upload2BCard({ clientId, period, onSuccess }: Upload2BCardProps) {
  const { uploadFile, loading, error, data } = useUpload2B(clientId, period);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;
    try {
      await uploadFile(selectedFile);
      onSuccess?.();
    } catch {
      // Error handled in hook state
    }
  };

  return (
    <div
      style={{
        border: "1px solid var(--hairline, rgba(0,0,0,0.06))",
        borderRadius: "6px",
        padding: "16px",
        marginBottom: "24px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h3 style={{ fontSize: "16px", fontWeight: 600, margin: 0 }}>Portal GSTR-2B File Upload</h3>
          <p style={{ fontSize: "13px", color: "#6B7280", margin: "4px 0 0 0" }}>
            Upload downloaded GST portal GSTR-2B JSON to reconcile against the Purchase Register.
          </p>
        </div>

        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            type="file"
            accept=".json"
            onChange={handleFileChange}
            style={{ fontSize: "13px" }}
          />
          <button
            onClick={handleUpload}
            disabled={!selectedFile || loading}
            style={{
              backgroundColor: "var(--royal, #2540D9)",
              color: "#fff",
              border: "none",
              borderRadius: "6px",
              padding: "8px 14px",
              fontSize: "13px",
              fontWeight: 500,
              cursor: !selectedFile || loading ? "not-allowed" : "pointer",
              opacity: !selectedFile || loading ? 0.6 : 1,
            }}
          >
            {loading ? "Reconciling..." : "Upload & Reconcile"}
          </button>
        </div>
      </div>

      {error && (
        <div
          style={{
            marginTop: "12px",
            padding: "10px",
            backgroundColor: "rgba(220,38,38,0.08)",
            color: "#DC2626",
            borderRadius: "6px",
            fontSize: "13px",
          }}
        >
          {error}
        </div>
      )}

      {data && (
        <div style={{ marginTop: "16px" }}>
          <div style={{ display: "flex", gap: "12px", marginBottom: "12px" }}>
            <span
              style={{
                backgroundColor: "rgba(37,64,217,0.1)",
                color: "var(--royal, #2540D9)",
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              Auto-Matched: {data.summary.autoMatched} (₹{(data.summary.totalAutoMatched / 100).toFixed(2)})
            </span>
            <span
              style={{
                backgroundColor: "rgba(220,38,38,0.1)",
                color: "#DC2626",
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
              }}
            >
              Unmatched: {data.summary.unmatched}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
