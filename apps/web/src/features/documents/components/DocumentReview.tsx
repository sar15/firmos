"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { ResizablePanelGroup, ResizablePanel, ResizableHandle } from "@/components/ui/resizable";
import { ExtractedDocument } from "@/types";
import dynamic from "next/dynamic";

const DocumentViewer = dynamic(() => import("./DocumentViewer").then(mod => mod.DocumentViewer), { ssr: false });

import { ExtractedFieldList } from "./ExtractedFieldList";
import { Button } from "@/components/ui/button";
import { approveDocumentAction, DocumentActionProposal, DocumentMapping, getReviewWorkspace, ReviewWorkspace, updateField, postToBooks, rejectDocument, markNeedsInfo } from "../documents.api";
import { DocumentMappingForm } from "./DocumentMappingForm";
import { ReviewSidebar } from "./ReviewSidebar";
import { AlertTriangle } from "lucide-react";

interface DocumentReviewProps {
  initialDocument: ExtractedDocument;
}

export function DocumentReview({ initialDocument }: DocumentReviewProps) {
  const router = useRouter();
  const [doc, setDoc] = useState<ExtractedDocument>(initialDocument);
  const [focusedFieldKey, setFocusedFieldKey] = useState<string | null>(null);
  const [isPosting, setIsPosting] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [proposal, setProposal] = useState<DocumentActionProposal | null>(null);
  const [mapping, setMapping] = useState<DocumentMapping>({});
  const [workspace, setWorkspace] = useState<ReviewWorkspace | null>(null);
  const provider = mapping.provider || "ZOHO_BOOKS";

  useEffect(() => {
    let active = true;
    getReviewWorkspace(initialDocument.id)
      .then(result => { if (active) setWorkspace(result); })
      .catch(() => { if (active) setWorkspace(null); });
    return () => { active = false; };
  }, [initialDocument.id]);

  const fields = doc.fields;
  const focusedBbox = useMemo(() => {
    if (!focusedFieldKey) return undefined;
    return fields.find(f => f.key === focusedFieldKey)?.bbox;
  }, [focusedFieldKey, fields]);

  const hasUnverifiedFields = useMemo(() => {
    return fields.some(f => f.level !== "HIGH");
  }, [fields]);
  const isSalesInvoice = doc.docKind === "SALES_INVOICE";

  const handleUpdateField = async (key: string, value: string) => {
    const fieldIndex = doc.fields.findIndex(f => f.key === key);
    if (fieldIndex === -1) return;
    
    // Save previous state for rollback
    const previousDoc = { ...doc };
    
    // Optimistic update locally
    const newFields = [...doc.fields];
    newFields[fieldIndex] = { ...newFields[fieldIndex], value, level: "HIGH", confidence: 1 };
    setDoc({ ...doc, fields: newFields });
    
    // Network update
    try {
      const updated = await updateField(doc.id, key, value);
      setDoc(updated);
      getReviewWorkspace(doc.id).then(setWorkspace).catch(() => undefined);
    } catch (e) {
      console.error("Failed to update field, rolling back:", e);
      setDoc(previousDoc); // Rollback
    }
  };

  const handlePost = useCallback(async () => {
    if (hasUnverifiedFields || isPosting) return;
    setIsPosting(true);
    try {
      const result = await postToBooks(doc.id, mapping);
      setProposal(result);
      getReviewWorkspace(doc.id).then(setWorkspace).catch(() => undefined);
      setToastMsg(result.status === "NEEDS_MAPPING" ? "Choose the matching Zoho records, then prepare again." : "Proposal ready. Review the exact action, then approve it.");
    } catch (e: unknown) {
      console.error(e);
      setToastMsg(e instanceof Error ? e.message : `Could not prepare the Zoho ${isSalesInvoice ? "invoice" : "bill"}`);
    } finally {
      setIsPosting(false);
    }
  }, [doc.id, hasUnverifiedFields, isPosting, isSalesInvoice, mapping]);

  const handleApprove = useCallback(async () => {
    if (!proposal?.action_id || !proposal.payload_hash || isPosting) return;
    setIsPosting(true);
    try {
      const result = await approveDocumentAction(proposal.action_id, proposal.payload_hash);
      if (result.status !== "QUEUED") throw new Error("The action could not be added to the verified execution queue.");
      setToastMsg("Queued for worker execution and provider read-back verification.");
      router.push("/documents");
    } catch (e: unknown) {
      setToastMsg(e instanceof Error ? e.message : "Could not approve the Zoho bill");
    } finally {
      setIsPosting(false);
    }
  }, [isPosting, proposal, router]);

  const handleReject = async () => {
    await rejectDocument(doc.id, "Rejected by CA");
    router.push("/documents");
  };

  const handleNeedsInfo = async () => {
    await markNeedsInfo(doc.id);
    router.push("/documents");
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // ⌘↵ to post
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handlePost();
        return;
      }
      
      // Esc to inbox
      if (e.key === "Escape") {
        router.push("/documents");
        return;
      }

      // J/K navigation
      if (e.target instanceof HTMLInputElement) return;

      if (e.key === "j" || e.key === "k") {
        const fields = doc.fields;
        const currentIndex = fields.findIndex(f => f.key === focusedFieldKey);
        let nextIndex = 0;
        
        if (e.key === "j") {
          nextIndex = currentIndex < fields.length - 1 ? currentIndex + 1 : 0;
        } else {
          nextIndex = currentIndex > 0 ? currentIndex - 1 : fields.length - 1;
        }
        setFocusedFieldKey(fields[nextIndex].key);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [doc.fields, focusedFieldKey, handlePost, router]);

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] bg-[var(--canvas)]">
      {toastMsg && (
        <div role="status" aria-live="polite" className="absolute top-4 left-1/2 -translate-x-1/2 z-50 bg-slate-900 text-white px-4 py-2 rounded shadow-lg text-sm font-medium animate-in fade-in slide-in-from-top-2">
          {toastMsg}
        </div>
      )}

      <ResizablePanelGroup direction="horizontal" className="flex-1 overflow-hidden">
        {/* Document pane gets a subtle var(--canvas) background by default (handled in viewer) */}
        <ResizablePanel defaultSize={58} minSize={30}>
          <DocumentViewer document={doc} focusedBbox={focusedBbox} />
        </ResizablePanel>
        
        <ResizableHandle className="w-1 bg-[var(--hairline)] hover:bg-[var(--royal)] transition-colors" />
        
        <ResizablePanel defaultSize={42} minSize={32}>
          <ResizablePanelGroup direction="horizontal">
            <ResizablePanel defaultSize={58} minSize={48}>
              <ExtractedFieldList
                document={doc}
                onUpdateField={handleUpdateField}
                onFocusField={setFocusedFieldKey}
                onBlurField={() => setFocusedFieldKey(null)}
                focusedFieldKey={focusedFieldKey}
              />
            </ResizablePanel>
            <ResizableHandle className="w-1 bg-[var(--hairline)] hover:bg-[var(--royal)] transition-colors" />
            <ResizablePanel defaultSize={42} minSize={34}>
              <ReviewSidebar workspace={workspace} provider={provider} onProviderChange={next => {
                setProposal(null);
                setMapping({ provider: next });
              }} />
            </ResizablePanel>
          </ResizablePanelGroup>
        </ResizablePanel>
      </ResizablePanelGroup>

      {/* Sticky Footer */}
      <div className="h-16 flex items-center justify-between px-6 bg-white border-t border-[var(--hairline)] shrink-0 z-20 relative">
        <div className="flex items-center gap-3">
          <Button variant="outline" className="text-red border-[var(--red)]/30 hover:bg-red/10" onClick={handleReject}>
            Reject
          </Button>
          <Button variant="outline" onClick={handleNeedsInfo}>
            Needs info
          </Button>
        </div>

        <div className="flex items-center gap-4">
          {hasUnverifiedFields && (
            <div className="flex items-center gap-1.5 text-xs text-amber font-medium mr-2">
              <AlertTriangle className="h-4 w-4" />
              Verify every extracted field before preparing a {isSalesInvoice ? "sales invoice" : "bill"}
            </div>
          )}
          {proposal && <DocumentMappingForm proposal={proposal} mapping={mapping} onChange={setMapping} />}
          {proposal?.action_id && proposal.payload_hash && (
            <div className="max-w-sm rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs text-slate-800" role="status">
              Ready to post. Approval is bound to this exact payload: <code className="font-mono">{proposal.payload_hash.slice(0, 12)}…</code>
            </div>
          )}
          <div className="flex items-center gap-3 text-xs text-muted font-medium">
            <span className="flex items-center gap-1"><kbd className="bg-hover border border-hairline rounded px-1.5 py-0.5">⌘</kbd> <kbd className="bg-hover border border-hairline rounded px-1.5 py-0.5">↵</kbd></span>
          </div>
          <Button 
            className="bg-[var(--royal)] hover:bg-[var(--royal)]/90 text-white active:scale-[0.98] transition-transform disabled:opacity-50"
            disabled={hasUnverifiedFields || isPosting}
            onClick={proposal?.action_id ? handleApprove : handlePost}
          >
            {isPosting ? "Working..." : proposal?.action_id ? `Approve & post to ${provider === "ZOHO_BOOKS" ? "Zoho Books" : "Tally"}` : proposal?.status === "NEEDS_MAPPING" ? "Prepare with selected mappings" : `Prepare ${provider === "ZOHO_BOOKS" ? "Zoho Books" : "Tally"} purchase`}
          </Button>
        </div>
      </div>
    </div>
  );
}
