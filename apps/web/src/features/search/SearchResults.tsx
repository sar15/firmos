"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { SearchResults as ISearchResults, searchEverything } from "@/features/clients/clients.api";
import { Row } from "@/components/Row";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { Search, Building, FileText, CheckSquare } from "lucide-react";
import { StatusDot } from "@/components/StatusDot";
import { MonoValue } from "@/components/MonoValue";
import { cn } from "@/lib/utils";

export function SearchResults() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const q = searchParams.get("q") || "";
  
  const [results, setResults] = useState<ISearchResults | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number>(-1);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!q) {
      setResults(null);
      return;
    }
    
    let isMounted = true;
    async function search() {
      setIsLoading(true);
      try {
        const data = await searchEverything(q);
        if (isMounted) setResults(data);
      } catch (e) {
        console.error(e);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }
    search();
    
    return () => { isMounted = false; };
  }, [q]);

  // Flatten items for keyboard navigation
  const flatItems = React.useMemo(() => {
    if (!results) return [];
    return [
      ...results.clients.map(c => ({ type: "client" as const, id: c.id, item: c, href: `/clients/${c.id}` })),
      ...results.decisions.map(d => ({ type: "decision" as const, id: d.id, item: d, href: `/decisions/${d.id}` })),
      ...results.documents.map(d => ({ type: "document" as const, id: d.id, item: d, href: `/documents/${d.id}` }))
    ];
  }, [results]);

  useEffect(() => {
    setSelectedIndex(-1);
  }, [q, flatItems.length]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (flatItems.length === 0) return;
      
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex(prev => (prev < flatItems.length - 1 ? prev + 1 : prev));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex(prev => (prev > 0 ? prev - 1 : prev));
      } else if (e.key === "Enter") {
        if (selectedIndex >= 0 && selectedIndex < flatItems.length) {
          e.preventDefault();
          router.push(flatItems[selectedIndex].href);
        }
      }
    };
    
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [flatItems, selectedIndex, router]);

  useEffect(() => {
    // Scroll selected item into view
    if (selectedIndex >= 0 && listRef.current) {
      const selectedEl = listRef.current.children[selectedIndex] as HTMLElement;
      if (selectedEl) {
        selectedEl.scrollIntoView({ block: "nearest" });
      }
    }
  }, [selectedIndex]);

  if (!q) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--canvas)] p-12">
        <EmptyState 
          icon={Search}
          title="Search FirmOS" 
          description="Type a query to search across clients, decisions, and documents."
        />
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex flex-col h-full bg-[var(--canvas)] p-6 gap-6">
        <Skeleton className="w-48 h-8" />
        <div className="flex flex-col gap-2">
          <Skeleton className="w-full h-16 rounded-md" />
          <Skeleton className="w-full h-16 rounded-md" />
          <Skeleton className="w-full h-16 rounded-md" />
        </div>
      </div>
    );
  }

  if (flatItems.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center bg-[var(--canvas)] p-12">
        <EmptyState 
          icon={Search}
          title={`No results for '${q}'`} 
          description="Try adjusting your search query or check for typos."
        />
      </div>
    );
  }

  let currentIndex = 0;

  return (
    <div className="flex flex-col h-full bg-[var(--canvas)] overflow-hidden">
      <div className="p-6 border-b border-[var(--hairline)] sticky top-0 bg-[var(--canvas)] z-10 shrink-0">
        <h1 className="text-xl font-semibold text-[var(--text)]">Search Results</h1>
        <p className="text-sm text-[var(--muted)] mt-1">
          Showing {flatItems.length} results for <span className="font-mono text-[var(--text)]">&apos;{q}&apos;</span>
        </p>
      </div>
      
      <div className="flex-1 overflow-y-auto p-6" ref={listRef}>
        <div className="flex flex-col gap-8 max-w-4xl mx-auto pb-12">
          {results && results.clients.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-2 flex items-center gap-2">
                <Building className="w-4 h-4" /> Clients
              </h2>
              <div className="flex flex-col bg-white border border-[var(--hairline)] rounded-md overflow-hidden">
                {results.clients.map((client) => {
                  const isSelected = selectedIndex === currentIndex;
                  const itemIndex = currentIndex++;
                  
                  return (
                    <Row
                      key={client.id}
                      onClick={() => {
                        setSelectedIndex(itemIndex);
                        router.push(`/clients/${client.id}`);
                      }}
                      className={cn(
                        "cursor-pointer px-4 mx-0 rounded-none border-b border-[var(--hairline)] last:border-none",
                        isSelected ? "bg-[var(--hover)]" : "hover:bg-[var(--hover)]"
                      )}
                    >
                      <div className="flex flex-col flex-1 py-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-[var(--text)]">{client.legalName}</span>
                          <StatusDot color={client.complianceStatus === "ON_TRACK" ? "royal" : client.complianceStatus === "DUE_SOON" ? "amber" : "red"} />
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-[var(--muted)]">
                          <span>PAN: <MonoValue>{client.pan}</MonoValue></span>
                          {client.gstin && <span>GSTIN: <MonoValue>{client.gstin}</MonoValue></span>}
                          <span>{client.entityType.replace("_", " ")}</span>
                        </div>
                      </div>
                    </Row>
                  );
                })}
              </div>
            </div>
          )}

          {results && results.decisions.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-2 flex items-center gap-2">
                <CheckSquare className="w-4 h-4" /> Decisions
              </h2>
              <div className="flex flex-col bg-white border border-[var(--hairline)] rounded-md overflow-hidden">
                {results.decisions.map((decision) => {
                  const isSelected = selectedIndex === currentIndex;
                  const itemIndex = currentIndex++;
                  
                  return (
                    <Row
                      key={decision.id}
                      onClick={() => {
                        setSelectedIndex(itemIndex);
                        router.push(`/decisions/${decision.id}`);
                      }}
                      className={cn(
                        "cursor-pointer px-4 mx-0 rounded-none border-b border-[var(--hairline)] last:border-none",
                        isSelected ? "bg-[var(--hover)]" : "hover:bg-[var(--hover)]"
                      )}
                    >
                      <div className="flex flex-col flex-1 py-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-[var(--text)]">{decision.title}</span>
                          <StatusDot color={decision.urgency === "NEEDS_YOU_NOW" ? "red" : decision.urgency === "DUE_TODAY" ? "amber" : "royal"} />
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-[var(--muted)]">
                          <span>Client ID: <MonoValue>{decision.clientId}</MonoValue></span>
                          <span className="truncate max-w-[400px]">Rec: {decision.firmOsRecommendation}</span>
                        </div>
                      </div>
                    </Row>
                  );
                })}
              </div>
            </div>
          )}

          {results && results.documents.length > 0 && (
            <div className="flex flex-col gap-2">
              <h2 className="text-sm font-semibold text-[var(--muted)] uppercase tracking-wider mb-2 flex items-center gap-2">
                <FileText className="w-4 h-4" /> Documents
              </h2>
              <div className="flex flex-col bg-white border border-[var(--hairline)] rounded-md overflow-hidden">
                {results.documents.map((doc) => {
                  const isSelected = selectedIndex === currentIndex;
                  const itemIndex = currentIndex++;
                  
                  return (
                    <Row
                      key={doc.id}
                      onClick={() => {
                        setSelectedIndex(itemIndex);
                        router.push(`/documents/${doc.id}`);
                      }}
                      className={cn(
                        "cursor-pointer px-4 mx-0 rounded-none border-b border-[var(--hairline)] last:border-none",
                        isSelected ? "bg-[var(--hover)]" : "hover:bg-[var(--hover)]"
                      )}
                    >
                      <div className="flex flex-col flex-1 py-1">
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-[var(--text)]">{doc.vendorName || "Unknown Vendor"}</span>
                          <StatusDot color={doc.status === "POSTED" ? "royal" : doc.status === "PENDING_REVIEW" ? "amber" : "red"} />
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-[var(--muted)]">
                          <span>{doc.clientName}</span>
                          <span>ID: <MonoValue>{doc.id}</MonoValue></span>
                        </div>
                      </div>
                    </Row>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
