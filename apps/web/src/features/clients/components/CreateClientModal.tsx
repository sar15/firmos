"use client";

import React, { useState } from "react";
import { X } from "lucide-react";
import { createClient, ClientCreateParams } from "../clients.api";
import { useRouter } from "next/navigation";

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export function CreateClientModal({ onClose, onSuccess }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [formData, setFormData] = useState<ClientCreateParams>({
    legalName: "",
    pan: "",
    gstin: "",
    entityType: "PRIVATE_LIMITED",
    state: "",
    booksProvider: "NONE"
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await createClient(formData);
      onSuccess();
      onClose();
      router.refresh();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create client");
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="w-[480px] bg-white rounded-[10px] shadow-lg border border-[var(--hairline)] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--hairline)] bg-[var(--canvas)]">
          <h2 className="text-sm font-semibold text-[var(--text)]">Add New Client</h2>
          <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--text)] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 flex flex-col gap-4">
          {error && <div className="text-red-500 text-xs text-center">{error}</div>}
          
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[var(--muted)]">Legal Name <span className="text-red-500">*</span></label>
            <input 
              type="text" 
              required
              value={formData.legalName}
              onChange={(e) => setFormData(prev => ({ ...prev, legalName: e.target.value }))}
              placeholder="Acme Corp" 
              className="h-10 px-3 border border-[var(--hairline)] rounded-[6px] text-[13px] w-full bg-white outline-none focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] transition-all"
            />
          </div>

          <div className="flex gap-4">
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-xs font-medium text-[var(--muted)]">PAN <span className="text-red-500">*</span></label>
              <input 
                type="text" 
                required
                value={formData.pan}
                onChange={(e) => setFormData(prev => ({ ...prev, pan: e.target.value.toUpperCase() }))}
                placeholder="ABCDE1234F" 
                className="h-10 px-3 border border-[var(--hairline)] rounded-[6px] text-[13px] w-full bg-white outline-none focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] transition-all uppercase font-mono"
              />
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-xs font-medium text-[var(--muted)]">GSTIN</label>
              <input 
                type="text" 
                value={formData.gstin}
                onChange={(e) => setFormData(prev => ({ ...prev, gstin: e.target.value.toUpperCase() }))}
                placeholder="27ABCDE1234F1Z5" 
                className="h-10 px-3 border border-[var(--hairline)] rounded-[6px] text-[13px] w-full bg-white outline-none focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] transition-all uppercase font-mono"
              />
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-xs font-medium text-[var(--muted)]">Entity Type</label>
              <select 
                value={formData.entityType}
                onChange={(e) => setFormData(prev => ({ ...prev, entityType: e.target.value }))}
                className="h-10 px-3 border border-[var(--hairline)] rounded-[6px] text-[13px] w-full bg-white outline-none focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] transition-all"
              >
                <option value="PRIVATE_LIMITED">Private Limited</option>
                <option value="LLP">LLP</option>
                <option value="PROPRIETOR">Proprietor</option>
                <option value="PARTNERSHIP">Partnership</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5 flex-1">
              <label className="text-xs font-medium text-[var(--muted)]">Books Provider</label>
              <select 
                value={formData.booksProvider}
                onChange={(e) => setFormData(prev => ({ ...prev, booksProvider: e.target.value }))}
                className="h-10 px-3 border border-[var(--hairline)] rounded-[6px] text-[13px] w-full bg-white outline-none focus:border-[var(--royal)] focus:ring-1 focus:ring-[var(--royal)] transition-all"
              >
                <option value="ZOHO_BOOKS">Zoho Books</option>
                <option value="TALLY">Tally</option>
                <option value="QUICKBOOKS">QuickBooks</option>
                <option value="CSV">CSV</option>
                <option value="NONE">None</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-3 mt-4">
            <button 
              type="button"
              onClick={onClose}
              disabled={loading}
              className="h-9 px-4 text-[13px] font-medium text-[var(--muted)] hover:text-[var(--text)] transition-colors"
            >
              Cancel
            </button>
            <button 
              type="submit" 
              disabled={loading}
              className="h-9 px-6 bg-[var(--royal)] hover:bg-[var(--royal-hover)] text-white rounded-[6px] text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)] focus-visible:ring-offset-2 disabled:opacity-50"
            >
              {loading ? "Adding..." : "Add Client"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
