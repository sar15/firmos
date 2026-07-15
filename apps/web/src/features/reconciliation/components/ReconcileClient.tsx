"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import type { ReconMode, ReconMatch } from "@/types";
import { ReconcileHeader } from "./ReconcileHeader";
import { ReconcileSummaryStrip } from "./ReconcileSummaryStrip";
import { MatchPane } from "./MatchPane";
import { acceptMatch, bulkAcceptClean, createBankProof, createGstr2bWorkpaper, decideBankCandidate,
  decideGstr2bMatch, EvidenceUploadResult, getBankWorkspace, getGstr2bWorkspace, getReconciliation,
  prepareBankCandidates, previewGstr2bBulk, rejectMatch } from "../reconciliation.api";
import { Skeleton } from "@/components/Skeleton";
import { formatIndianRupee } from "@/lib/formatIndianRupee";

interface ReconcileClientProps {
  clientId: string;
}

export function ReconcileClient({ clientId }: ReconcileClientProps) {
  const [clientName, setClientName] = useState("Client");
  const [mode, setMode] = useState<ReconMode>("BANK_STATEMENT");
  const [matches, setMatches] = useState<ReconMatch[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [focusedId, setFocusedId] = useState<string | null>(null);
  const [isAccepting, setIsAccepting] = useState(false);
  const [period, setPeriod] = useState("062026");
  const [evidence, setEvidence] = useState<{ id: string; mode: ReconMode; message: string } | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  // Computed buckets
  const suggested = useMemo(() => matches.filter(m => m.status === "SUGGESTED"), [matches]);
  const unmatched = useMemo(() => matches.filter(m => m.status === "UNMATCHED"), [matches]);
  const autoMatched = useMemo(() => matches.filter(m => m.status === "AUTO_MATCHED"), [matches]);
  
  // Flattened for keyboard nav
  const activeItems = useMemo(() => [...suggested, ...unmatched, ...autoMatched], [suggested, unmatched, autoMatched]);

  const loadData = useCallback(async (currentMode: ReconMode) => {
    setIsLoading(true);
    try {
      const { getClient } = await import("@/features/clients/clients.api");
      const [data, clientData] = await Promise.all([
        getReconciliation(clientId, currentMode, period),
        getClient(clientId).catch(() => ({ legalName: "Unknown Client" }))
      ]);
      setMatches(data.matches);
      setClientName(clientData.legalName);
      // Auto-focus first suggested or unmatched
      const firstActive = data.matches.find(m => m.status !== "AUTO_MATCHED");
      if (firstActive) setFocusedId(firstActive.id);
    } catch (e) {
      setActionMessage(e instanceof Error ? e.message : "Reconciliation data could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }, [clientId, period]);

  useEffect(() => {
    loadData(mode);
  }, [mode, loadData]);

  const moveFocusDown = useCallback((currentId: string) => {
    const idx = activeItems.findIndex(m => m.id === currentId);
    if (idx !== -1 && idx < activeItems.length - 1) {
      setFocusedId(activeItems[idx + 1].id);
    }
  }, [activeItems]);

  const moveFocusUp = useCallback((currentId: string) => {
    const idx = activeItems.findIndex(m => m.id === currentId);
    if (idx > 0) {
      setFocusedId(activeItems[idx - 1].id);
    }
  }, [activeItems]);

  const refreshEvidence = useCallback(async () => {
    if (!evidence) return loadData(mode);
    setMatches(evidence.mode === "GSTR2B_VS_PURCHASE"
      ? await getGstr2bWorkspace(evidence.id) : await getBankWorkspace(evidence.id));
  }, [evidence, loadData, mode]);

  const handleUpload = async (result: EvidenceUploadResult) => {
    if (result.identityErrors?.length) {
      setActionMessage("File identity does not match this client or period. Correct the selection before reconciling.");
      return;
    }
    setActionMessage(result.duplicateUpload ? "This exact file was already imported; showing the existing run." : "Evidence imported and checked successfully.");
    if (result.runId) {
      setEvidence({ id: result.runId, mode, message: "Official 2B import" });
      setMatches(await getGstr2bWorkspace(result.runId));
    } else if (result.statementId) {
      await prepareBankCandidates(result.statementId);
      setEvidence({ id: result.statementId, mode, message: result.balanceValidation?.valid ? "Statement balance checked" : "Statement needs balance review" });
      setMatches(await getBankWorkspace(result.statementId));
    }
  };

  const handleAccept = useCallback(async (id: string) => {
    try {
      const match = matches.find(item => item.id === id);
      if (!match) return;
      if (evidence?.mode === "GSTR2B_VS_PURCHASE") await decideGstr2bMatch(id, true);
      else if (evidence?.mode === "BANK_STATEMENT") await decideBankCandidate(id, true);
      else await acceptMatch(match, clientId, mode, period);
      await refreshEvidence();
      moveFocusDown(id);
    } catch (e) {
      setActionMessage(e instanceof Error ? e.message : "The match could not be accepted.");
    }
  }, [clientId, evidence, matches, mode, moveFocusDown, period, refreshEvidence]);

  const handleReject = useCallback(async (id: string) => {
    try {
      const match = matches.find(item => item.id === id);
      if (!match) return;
      if (evidence?.mode === "GSTR2B_VS_PURCHASE") await decideGstr2bMatch(id, false);
      else if (evidence?.mode === "BANK_STATEMENT") await decideBankCandidate(id, false);
      else await rejectMatch(match, clientId, mode, period);
      await refreshEvidence();
      moveFocusDown(id);
    } catch (e) {
      setActionMessage(e instanceof Error ? e.message : "The match could not be rejected.");
    }
  }, [clientId, evidence, matches, mode, moveFocusDown, period, refreshEvidence]);

  const handleUndo = async (id: string) => {
    // For MVP, undoing an auto-matched item reverts it to unmatched.
    try {
      const match = matches.find(item => item.id === id);
      if (!match) return;
      if (evidence?.mode === "GSTR2B_VS_PURCHASE") await decideGstr2bMatch(id, false);
      else if (evidence?.mode === "BANK_STATEMENT") await decideBankCandidate(id, false);
      else await rejectMatch(match, clientId, mode, period);
      await refreshEvidence();
      setFocusedId(id);
    } catch (e) {
      setActionMessage(e instanceof Error ? e.message : "The match could not be changed.");
    }
  };

  const handleBulkAcceptClean = async () => {
    setIsAccepting(true);
    try {
      if (evidence?.mode === "GSTR2B_VS_PURCHASE") {
        const preview = await previewGstr2bBulk(evidence.id);
        if (!preview.count || !window.confirm(`Accept ${preview.count} exact matches totalling ${formatIndianRupee(preview.total_paise)}?`)) return;
        await previewGstr2bBulk(evidence.id, true);
        setActionMessage(`${preview.count} clean matches accepted. No portal action was performed.`);
      } else {
        await bulkAcceptClean(clientId, mode, period);
      }
      await refreshEvidence();
    } catch (e) {
      setActionMessage(e instanceof Error ? e.message : "Clean matches could not be accepted.");
    } finally {
      setIsAccepting(false);
    }
  };

  const handleProof = async () => {
    if (!evidence) return;
    try {
      const result = evidence.mode === "GSTR2B_VS_PURCHASE"
        ? await createGstr2bWorkpaper(evidence.id) : await createBankProof(evidence.id);
      setActionMessage(`Version ${result.version} created with current decisions and unresolved items.`);
    } catch (error) {
      setActionMessage(error instanceof Error ? error.message : "Proof could not be created.");
    }
  };

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (!focusedId) return;

      const focusedMatch = activeItems.find(m => m.id === focusedId);
      if (!focusedMatch) return;

      if (e.key === "j") {
        e.preventDefault();
        moveFocusDown(focusedId);
      } else if (e.key === "k") {
        e.preventDefault();
        moveFocusUp(focusedId);
      } else if (e.key === "a" && focusedMatch.status === "SUGGESTED") {
        e.preventDefault();
        handleAccept(focusedId);
      } else if (e.key === "x" && focusedMatch.status === "SUGGESTED") {
        e.preventDefault();
        handleReject(focusedId);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [focusedId, activeItems, handleAccept, handleReject, moveFocusDown, moveFocusUp]);

  // Compute summary values locally to reflect optimistic/immediate updates without refetching
  const summary = {
    autoMatched: autoMatched.length,
    suggested: suggested.length,
    unmatched: unmatched.length,
    totalAutoMatched: autoMatched.reduce((acc, m) => acc + m.source.amount, 0),
    totalSuggested: suggested.reduce((acc, m) => acc + m.source.amount, 0),
    totalUnmatched: unmatched.reduce((acc, m) => acc + m.source.amount, 0),
  };

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] bg-[var(--canvas)]">
      <ReconcileHeader
        clientId={clientId}
        clientName={clientName}
        mode={mode}
        onModeChange={(nextMode) => { setEvidence(null); setActionMessage(null); setMode(nextMode); }}
        onUploadSuccess={handleUpload}
        period={period}
        onPeriodChange={(nextPeriod) => { setEvidence(null); setActionMessage(null); setPeriod(nextPeriod); }}
      />
      {(evidence || actionMessage) && (
        <div className="flex flex-col gap-2 border-b border-[var(--hairline)] bg-slate-50 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between sm:px-6" aria-live="polite">
          <div><strong className="text-[var(--text)]">{evidence?.message || "Review required"}</strong><span className="ml-2 text-[var(--muted)]">{actionMessage}</span></div>
          {evidence && <button onClick={handleProof} className="min-h-11 cursor-pointer rounded-md border border-[var(--hairline)] bg-white px-4 font-medium text-[var(--text)] hover:bg-[var(--hover)]">Create versioned proof</button>}
        </div>
      )}
      
      <ReconcileSummaryStrip 
        summary={summary} 
        onBulkAcceptClean={handleBulkAcceptClean}
        isAccepting={isAccepting}
      />

      {/* Keyboard hints footer (floating) */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-50 hidden sm:flex items-center gap-4 bg-[var(--panel)] border border-[var(--hairline)] text-[var(--text)] px-6 py-2 rounded-full shadow-lg text-xs font-medium backdrop-blur">
        <span><kbd className="text-[var(--muted-2)]">J/K</kbd> move</span>
        <span><kbd className="text-[var(--muted-2)]">A</kbd> accept</span>
        <span><kbd className="text-[var(--muted-2)]">X</kbd> reject</span>
      </div>

      <div className="flex-1 overflow-hidden relative">
        {isLoading ? (
          <div className="p-6 flex flex-col gap-2 h-full">
            <Skeleton className="w-full h-[73px]" />
            <Skeleton className="w-full h-[73px]" />
            <Skeleton className="w-full h-[73px]" />
            <Skeleton className="w-full h-[73px]" />
          </div>
        ) : (
          <MatchPane
            suggested={suggested}
            unmatched={unmatched}
            matched={autoMatched}
            focusedId={focusedId}
            onAccept={handleAccept}
            onReject={handleReject}
            onUndo={handleUndo}
          />
        )}
      </div>
    </div>
  );
}
