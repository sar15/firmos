"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { ExtractedDocument, Client } from "@/types";
import { listDocuments, uploadDocument } from "../documents.api";
import { listClients } from "@/features/clients/clients.api";
import { formatIndianRupee } from "@/lib/formatIndianRupee";
import { formatComplianceDate } from "@/lib/formatComplianceDate";
import { Row } from "@/components/Row";
import { MonoValue } from "@/components/MonoValue";
import { StatusDot, StatusDotColor } from "@/components/StatusDot";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { ConfidenceBadge } from "./ConfidenceBadge";
import { FileText, Upload, Loader2, ChevronDown } from "lucide-react";

export function DocumentInbox() {
  const router = useRouter();
  const [documents, setDocuments] = useState<ExtractedDocument[]>([]);
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<string>("PENDING_REVIEW");
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [docsData, clientsData] = await Promise.all([
        listDocuments(),
        listClients()
      ]);
      setDocuments(docsData);
      setClients(clientsData);
      setSelectedClientId(current => current || clientsData[0]?.id || "");
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!selectedClientId) {
      alert("Please select a client first.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }

    const client = clients.find(c => c.id === selectedClientId);
    
    setIsUploading(true);
    try {
      await uploadDocument(file, selectedClientId, client?.legalName || "Unknown Client");
      await load();
    } catch (error) {
      console.error("Upload failed", error);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const filtered = documents.filter((d) => 
    filter === "ALL" ? true : d.status === filter
  );

  const getWorstConfidence = (doc: ExtractedDocument) => {
    if (doc.fields.some(f => f.level === "LOW")) return "LOW";
    if (doc.fields.some(f => f.level === "REVIEW")) return "REVIEW";
    return "HIGH";
  };

  const getStatusColor = (status: string): StatusDotColor => {
    switch (status) {
      case "PENDING_REVIEW": return "amber";
      case "POSTED": return "royal";
      case "REJECTED": return "red";
      case "NEEDS_INFO": return "red";
      default: return "slate";
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col h-full bg-[var(--canvas)]">
        <div className="p-6 border-b border-[var(--hairline)] bg-[var(--canvas)] flex items-center justify-between">
          <Skeleton className="w-32 h-6" />
          <Skeleton className="w-48 h-8 rounded-md" />
        </div>
        <div className="flex-1 p-6 flex flex-col gap-2">
          <Skeleton className="w-full h-16 rounded" />
          <Skeleton className="w-full h-16 rounded" />
          <Skeleton className="w-full h-16 rounded" />
        </div>
      </div>
    );
  }

  const pendingCount = documents.filter(d => d.status === "PENDING_REVIEW").length;
  const unreadCount = documents.length; // placeholder

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] bg-[var(--canvas)]">
      <div className="p-4 border-b border-[var(--hairline)] flex items-center justify-between sticky top-0 bg-[var(--canvas)] z-10">
        <h2 className="text-lg font-semibold text-[var(--text)]">Document Inbox</h2>
        <div className="flex items-center gap-4">
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleUpload} 
            className="hidden" 
            accept="image/*,application/pdf"
          />
          
          <div className="flex items-center gap-2 relative">
            <select 
              value={selectedClientId} 
              onChange={e => setSelectedClientId(e.target.value)}
              className="appearance-none pl-3 pr-8 py-1.5 bg-[var(--canvas)] border border-[var(--hairline)] rounded-md text-sm outline-none focus:border-[var(--royal)] text-[var(--text)] w-48 truncate"
            >
              <option value="" disabled>Select Client</option>
              {clients.map(c => (
                <option key={c.id} value={c.id}>{c.legalName}</option>
              ))}
            </select>
            <ChevronDown className="w-4 h-4 text-[var(--muted)] absolute right-2 pointer-events-none" />
          </div>

          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || !selectedClientId}
            className="flex items-center gap-2 px-3 py-1.5 bg-[var(--royal)] hover:bg-blue-700 text-white text-sm font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            {isUploading ? "Uploading..." : "Upload Bill"}
          </button>
          
          <div className="flex items-center gap-1.5 px-2 py-1 bg-[var(--amber)]/10 border border-[var(--amber)]/20 rounded-md text-[var(--amber)] text-xs font-medium ml-4">
            <StatusDot color="amber" />
            <span>{pendingCount} Pending</span>
          </div>
          <div className="flex items-center gap-1.5 px-2 py-1 bg-[var(--hover)] border border-[var(--hairline)] rounded-md text-[var(--text)] text-xs font-medium">
            <span className="font-mono tabular-nums">{unreadCount}</span>
            <span>Unread</span>
          </div>
        </div>
      </div>
      
      <div className="p-4 border-b border-[var(--hairline)] bg-[var(--canvas)] flex flex-col gap-4 sticky top-[64px] z-10">
        <div className="flex items-center justify-between">
          <div className="flex bg-[var(--hover)] p-1 rounded-md text-sm font-medium border border-[var(--hairline)]">
            <button 
              className={`px-3 py-1.5 rounded-sm transition-colors ${filter === "PENDING_REVIEW" ? "bg-[var(--canvas)] text-[var(--text)]" : "text-[var(--muted)] hover:text-[var(--text)]"}`}
              onClick={() => setFilter("PENDING_REVIEW")}
            >
              Action Required
            </button>
            <button 
              className={`px-3 py-1.5 rounded-sm transition-colors ${filter === "POSTED" ? "bg-[var(--canvas)] text-[var(--text)]" : "text-[var(--muted)] hover:text-[var(--text)]"}`}
              onClick={() => setFilter("POSTED")}
            >
              Posted
            </button>
            <button 
              className={`px-3 py-1.5 rounded-sm transition-colors ${filter === "ALL" ? "bg-[var(--canvas)] text-[var(--text)]" : "text-[var(--muted)] hover:text-[var(--text)]"}`}
              onClick={() => setFilter("ALL")}
            >
              All
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="p-12 h-full flex items-center justify-center">
            <EmptyState 
              icon={FileText}
              title="No documents found" 
              description={filter === "PENDING_REVIEW" ? "You're all caught up. No documents need your review." : "No documents match this filter."}
            />
          </div>
        ) : (
          <div className="flex flex-col bg-[var(--canvas)] border-y border-[var(--hairline)] mt-6">
            {filtered.map((doc) => (
              <Row
                key={doc.id}
                onClick={() => router.push(`/documents/${doc.id}`)}
                className="cursor-pointer hover:bg-[var(--hover)] transition-colors px-6 mx-0 rounded-none border-b border-[var(--hairline)] last:border-none"
              >
                 <div className="flex items-center justify-between w-full">
                    <div className="flex items-center gap-4">
                      <StatusDot color={getStatusColor(doc.status)} />
                      <div className="flex flex-col">
                        <span className="font-medium text-[var(--text)]">{doc.vendorName}</span>
                        <span className="text-sm text-[var(--muted)]">{doc.clientName}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-8">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-[var(--muted)] uppercase tracking-wider font-medium">Confidence</span>
                        <ConfidenceBadge level={getWorstConfidence(doc)} showLabel={false} />
                      </div>
                      <MonoValue>{formatIndianRupee(doc.total)}</MonoValue>
                      <span className="text-sm text-[var(--muted-2)] w-24 text-right">
                        {formatComplianceDate(doc.uploadedAt)}
                      </span>
                    </div>
                 </div>
              </Row>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
