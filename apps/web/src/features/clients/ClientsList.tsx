"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Client } from "@/types";
import { listClients, ListClientsFilter } from "./clients.api";
import { Row } from "@/components/Row";
import { MonoValue } from "@/components/MonoValue";
import { StatusDot, StatusDotColor } from "@/components/StatusDot";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/Skeleton";
import { Search, Users, Plus } from "lucide-react";
import { CreateClientModal } from "./components/CreateClientModal";
import { PageHeader } from "@/components/PageHeader";

export function ClientsList() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  
  const [filter, setFilter] = useState<ListClientsFilter>({});
  const [sortConfig, setSortConfig] = useState<{ key: keyof Client; direction: "asc" | "desc" } | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await listClients(filter);
      setClients(data);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  const sortedClients = useMemo(() => {
    const sortableItems = [...clients];
    if (sortConfig !== null) {
      sortableItems.sort((a, b) => {
        const aValue = a[sortConfig.key];
        const bValue = b[sortConfig.key];

        if (aValue === null && bValue !== null) return sortConfig.direction === "asc" ? 1 : -1;
        if (aValue !== null && bValue === null) return sortConfig.direction === "asc" ? -1 : 1;
        if (aValue === bValue) return 0;
        if (aValue === null || bValue === null) return 0;

        if (aValue < bValue) {
          return sortConfig.direction === "asc" ? -1 : 1;
        }
        if (aValue > bValue) {
          return sortConfig.direction === "asc" ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableItems;
  }, [clients, sortConfig]);

  const requestSort = (key: keyof Client) => {
    let direction: "asc" | "desc" = "asc";
    if (sortConfig && sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  const getStatusColor = (status: string): StatusDotColor => {
    switch (status) {
      case "ON_TRACK": return "royal";
      case "DUE_SOON": return "amber";
      case "OVERDUE": return "red";
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
          <Skeleton className="w-full h-12 rounded-sm" />
          <Skeleton className="w-full h-12 rounded-sm" />
          <Skeleton className="w-full h-12 rounded-sm" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-56px)] bg-[var(--canvas)]">
      <PageHeader 
        title="Clients"
        meta={
          <>
            <span className="font-mono text-sm tabular-nums text-[var(--muted)]">{clients.length} Total</span>
            <button 
              onClick={() => setIsCreateModalOpen(true)}
              className="h-8 px-3 bg-[var(--royal)] hover:bg-[var(--royal-hover)] text-white text-xs font-medium rounded-[6px] transition-colors flex items-center gap-1.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--royal)] focus-visible:ring-offset-2"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Client
            </button>
          </>
        }
      >
        <div className="relative">
          <Search className="absolute left-2.5 top-1.5 h-4 w-4 text-[var(--muted)]" />
          <input 
            type="text" 
            placeholder="Search clients..." 
            className="pl-8 pr-3 py-1.5 border border-[var(--hairline)] rounded-md bg-white text-[var(--text)] outline-none focus:border-[var(--royal)] w-64 transition-colors"
            onChange={(e) => setFilter(f => ({ ...f, search: e.target.value }))}
          />
        </div>
        
        <select 
          className="px-3 py-1.5 border border-[var(--hairline)] rounded-md bg-white text-[var(--text)] outline-none"
          onChange={(e) => setFilter(f => ({ ...f, entityType: e.target.value || undefined }))}
        >
          <option value="">All Entities</option>
          <option value="PRIVATE_LIMITED">Private Limited</option>
          <option value="LLP">LLP</option>
          <option value="PROPRIETOR">Proprietor</option>
          <option value="PARTNERSHIP">Partnership</option>
        </select>
        
        <select 
          className="px-3 py-1.5 border border-[var(--hairline)] rounded-md bg-white text-[var(--text)] outline-none"
          onChange={(e) => setFilter(f => ({ ...f, status: e.target.value || undefined }))}
        >
          <option value="">All Statuses</option>
          <option value="ON_TRACK">On Track</option>
          <option value="DUE_SOON">Due Soon</option>
          <option value="OVERDUE">Overdue</option>
        </select>
        
        <select 
          className="px-3 py-1.5 border border-[var(--hairline)] rounded-md bg-white text-[var(--text)] outline-none"
          onChange={(e) => setFilter(f => ({ ...f, booksProvider: e.target.value || undefined }))}
        >
          <option value="">All Providers</option>
          <option value="ZOHO_BOOKS">Zoho Books</option>
          <option value="TALLY">Tally</option>
          <option value="QUICKBOOKS">QuickBooks</option>
          <option value="CSV">CSV</option>
          <option value="NONE">None</option>
        </select>
      </PageHeader>

      <div className="flex-1 overflow-y-auto">
        {sortedClients.length === 0 ? (
          <div className="p-12 h-full flex items-center justify-center">
            <EmptyState 
              icon={Users}
              title="No clients match" 
              description="Try adjusting your filters or search query."
            />
          </div>
        ) : (
          <div className="flex flex-col bg-[var(--canvas)] border-y border-[var(--hairline)] mt-6 min-w-[800px]">
            {/* Table Header */}
            <div className="flex items-center justify-between px-6 py-2 border-b border-[var(--hairline)] bg-[var(--hover)] text-xs font-semibold text-[var(--muted)] uppercase tracking-wider sticky top-0 z-10">
              <div className="w-1/4 cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("legalName")}>
                Client Name {sortConfig?.key === "legalName" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
              <div className="w-32 cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("pan")}>
                PAN {sortConfig?.key === "pan" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
              <div className="w-36 cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("gstin")}>
                GSTIN {sortConfig?.key === "gstin" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
              <div className="w-32 cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("entityType")}>
                Entity {sortConfig?.key === "entityType" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
              <div className="w-32 cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("booksProvider")}>
                Books {sortConfig?.key === "booksProvider" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
              <div className="w-24 text-right cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("nextDue")}>
                Next Due {sortConfig?.key === "nextDue" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
              <div className="w-24 text-right cursor-pointer hover:text-[var(--text)]" onClick={() => requestSort("complianceStatus")}>
                Status {sortConfig?.key === "complianceStatus" && (sortConfig.direction === "asc" ? "↑" : "↓")}
              </div>
            </div>
            
            {/* Table Rows */}
            {sortedClients.map((client) => (
              <Row
                key={client.id}
                onClick={() => router.push(`/clients/${client.id}`)}
                className="cursor-pointer hover:bg-[var(--hover)] transition-colors px-6 mx-0 rounded-none border-b border-[var(--hairline)] last:border-none"
              >
                <div className="w-1/4 text-sm font-medium text-[var(--text)] pr-4 truncate">
                  {client.legalName}
                </div>
                <div className="w-32 pr-4">
                  <MonoValue className="text-left">{client.pan}</MonoValue>
                </div>
                <div className="w-36 pr-4">
                  <MonoValue className="text-left">{client.gstin || "—"}</MonoValue>
                </div>
                <div className="w-32 pr-4 text-sm text-[var(--muted)]">
                  {client.entityType.replace("_", " ")}
                </div>
                <div className="w-32 pr-4 text-sm text-[var(--muted)]">
                  {client.booksProvider ? client.booksProvider.replace("_", " ") : "—"}
                </div>
                <div className="w-24 text-right pr-4">
                  <MonoValue>{client.nextDue || "—"}</MonoValue>
                </div>
                <div className="w-24 flex items-center justify-end gap-2">
                  <span className="text-xs font-medium text-[var(--muted)]">{client.complianceStatus.replace("_", " ")}</span>
                  <StatusDot color={getStatusColor(client.complianceStatus)} />
                </div>
              </Row>
            ))}
          </div>
        )}
      </div>

      {isCreateModalOpen && (
        <CreateClientModal 
          onClose={() => setIsCreateModalOpen(false)} 
          onSuccess={() => load()} 
        />
      )}
    </div>
  );
}
