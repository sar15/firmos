import React, { useRef, useState } from "react";
import { ReconMode } from "@/types";
import { Upload, Loader2 } from "lucide-react";
import { EvidenceUploadResult, uploadEvidence } from "../reconciliation.api";

interface ReconcileHeaderProps {
  clientId: string;
  clientName: string;
  mode: ReconMode;
  onModeChange: (mode: ReconMode) => void;
  onUploadSuccess: (result: EvidenceUploadResult) => Promise<void> | void;
  period: string;
  onPeriodChange: (period: string) => void;
}

export function ReconcileHeader({ clientId, clientName, mode, onModeChange, onUploadSuccess, period, onPeriodChange }: ReconcileHeaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsUploading(true);
    setUploadError(null);
    try {
      await onUploadSuccess(await uploadEvidence(file, clientId, period, mode));
    } catch (e) {
      console.error(e);
      setUploadError(e instanceof Error ? e.message : "Upload failed. Check the file and try again.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <div className="flex flex-col gap-4 px-4 py-4 sm:px-6 bg-white border-b border-[var(--hairline)] shrink-0">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-col">
        <h1 className="text-xl font-semibold text-text">Reconciliation Workspace</h1>
        <span className="text-sm text-muted">{clientName} · Review one period with source evidence kept intact</span>
      </div>
      
      <div className="flex flex-wrap items-end gap-3">
        {mode === "BANK_STATEMENT" && (
          <div className="flex items-center">
            <input 
              type="file" 
              ref={fileInputRef} 
              onChange={handleUpload} 
              className="hidden" 
              accept=".csv,.xls,.xlsx,.pdf"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className="flex min-h-11 cursor-pointer items-center gap-2 px-4 bg-[var(--royal)] hover:bg-blue-700 text-white text-sm font-medium rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {isUploading ? "Checking file..." : "Upload statement"}
            </button>
          </div>
        )}
        {mode === "GSTR2B_VS_PURCHASE" && (
          <div className="flex items-center">
            <input type="file" ref={fileInputRef} onChange={handleUpload} className="hidden" accept=".json,.xls,.xlsx" />
            <button onClick={() => fileInputRef.current?.click()} disabled={isUploading} className="flex min-h-11 cursor-pointer items-center gap-2 px-4 bg-[var(--royal)] hover:bg-blue-700 text-white text-sm font-medium rounded-md transition-colors disabled:cursor-not-allowed disabled:opacity-50">
              {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
              {isUploading ? "Checking identity..." : "Upload official 2B"}
            </button>
          </div>
        )}

        <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
          Period
          <input
            aria-label="Reconciliation period"
            type="month"
            value={`${period.slice(2)}-${period.slice(0, 2)}`}
            onChange={(event) => {
              const [year, month] = event.target.value.split("-");
              if (year && month) onPeriodChange(`${month}${year}`);
            }}
            className="h-11 rounded-md border border-[var(--hairline)] bg-white px-3 text-base sm:text-sm text-[var(--text)]"
          />
        </label>

        {/* Segmented Mode Toggle */}
        <div className="flex bg-hover p-1 rounded-md text-sm font-medium border border-hairline">
          <button 
            className={`min-h-11 cursor-pointer px-4 rounded-sm transition-colors ${mode === "BANK_STATEMENT" ? "bg-white text-[var(--royal)]" : "text-muted hover:text-slate-700"}`}
            onClick={() => onModeChange("BANK_STATEMENT")}
          >
            Bank ↔ Books
          </button>
          <button 
            className={`min-h-11 cursor-pointer px-4 rounded-sm transition-colors ${mode === "GSTR2B_VS_PURCHASE" ? "bg-white text-[var(--royal)]" : "text-muted hover:text-slate-700"}`}
            onClick={() => onModeChange("GSTR2B_VS_PURCHASE")}
          >
            GSTR-2B ↔ Purchases
          </button>
        </div>
      </div>
      </div>
      <div className="grid gap-2 text-sm text-[var(--muted)] sm:grid-cols-3" aria-label="Reconciliation steps">
        <span><strong className="text-[var(--text)]">1. Upload</strong> official evidence</span>
        <span><strong className="text-[var(--text)]">2. Review</strong> matches and warnings</span>
        <span><strong className="text-[var(--text)]">3. Confirm</strong> decisions and proof</span>
      </div>
      {uploadError && <p role="alert" className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{uploadError}</p>}
    </div>
  );
}
