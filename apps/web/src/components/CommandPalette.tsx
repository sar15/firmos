"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { Search, Compass, CheckSquare, FileText, Zap, Shield, Settings, Play, CheckCircle2, Building } from "lucide-react";
import { searchEverything } from "@/features/clients/clients.api";
import type { Client } from "@/types";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [clients, setClients] = useState<Client[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  // Handle keyboard shortcut
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "k" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
    };
    document.addEventListener("keydown", down);
    
    // Listen to custom event from TopBar
    const handleCustomOpen = () => setOpen(true);
    window.addEventListener("open-command-palette", handleCustomOpen);

    return () => {
      document.removeEventListener("keydown", down);
      window.removeEventListener("open-command-palette", handleCustomOpen);
    };
  }, []);

  // Debounce query for client search
  useEffect(() => {
    if (!query) {
      setClients([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const results = await searchEverything(query);
        setClients(results.clients);
      } catch (e) {
        console.error(e);
      } finally {
        setIsLoading(false);
      }
    }, 120);
    return () => clearTimeout(timer);
  }, [query]);

  const runCommand = (command: () => void) => {
    setOpen(false);
    command();
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/40 backdrop-blur-[2px] transition-opacity" 
        onClick={() => setOpen(false)}
      />
      
      {/* Dialog */}
      <div className="relative w-full max-w-[560px] bg-white rounded-[10px] shadow-[0_16px_70px_rgba(0,0,0,0.2)] overflow-hidden border border-[var(--hairline)] flex flex-col animate-in fade-in zoom-in-95 duration-150">
        <Command
          label="Global Command Menu"
          shouldFilter={false}
          className="flex flex-col h-full w-full outline-none"
        >
          <div className="flex items-center px-4 border-b border-[var(--hairline)]">
            <Search className="w-4 h-4 text-[var(--muted-2)] shrink-0" strokeWidth={1.5} />
            <Command.Input
              value={query}
              onValueChange={setQuery}
              autoFocus
              placeholder="Search or jump to..."
              className="flex-1 h-12 bg-transparent outline-none px-3 text-[13px] text-[var(--text)] placeholder:text-[var(--muted-2)]"
            />
            {isLoading && <div className="w-3 h-3 border-2 border-[var(--royal)] border-t-transparent rounded-full animate-spin shrink-0"></div>}
            <div className="flex items-center gap-1 text-[10px] text-[var(--muted-2)] font-mono shrink-0 ml-3 bg-[var(--hover)] px-1.5 py-0.5 rounded border border-[var(--hairline)]">
              ESC
            </div>
          </div>

          <Command.List className="max-h-[360px] overflow-y-auto p-2 outline-none">
            <Command.Empty className="py-8 text-center text-[13px] text-[var(--muted)]">
              No results found for &quot;{query}&quot;.
            </Command.Empty>

            {clients.length > 0 && (
              <Command.Group heading="Clients" className="px-2 py-1.5 text-[11px] font-semibold text-[var(--muted-2)] uppercase tracking-wider">
                {clients.map(c => (
                  <Command.Item
                    key={c.id}
                    onSelect={() => runCommand(() => router.push(`/clients/${c.id}`))}
                    className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors"
                  >
                    <Building className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                    <span className="flex-1">{c.legalName}</span>
                    <span className="text-[11px] font-mono text-[var(--muted)] group-aria-selected:text-[var(--royal)]/70">{c.pan}</span>
                  </Command.Item>
                ))}
              </Command.Group>
            )}

            {!query && (
              <Command.Group heading="Navigate" className="px-2 py-1.5 text-[11px] font-semibold text-[var(--muted-2)] uppercase tracking-wider">
                <Command.Item onSelect={() => runCommand(() => router.push('/'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <CheckSquare className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Decisions</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <Zap className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Work Stream</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/connectors'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <Compass className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Connectors</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/clients'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <Building className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Clients</span>
                  <span className="text-[10px] font-mono text-[var(--muted)] bg-[var(--hover)] px-1.5 rounded border border-[var(--hairline)] group-aria-selected:border-transparent group-aria-selected:bg-transparent">G C</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/audit'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <Shield className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Audit</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/settings/profile'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <Settings className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Settings</span>
                  <span className="text-[10px] font-mono text-[var(--muted)] bg-[var(--hover)] px-1.5 rounded border border-[var(--hairline)] group-aria-selected:border-transparent group-aria-selected:bg-transparent">,</span>
                </Command.Item>
              </Command.Group>
            )}

            {!query && (
              <Command.Group heading="Actions" className="px-2 py-1.5 text-[11px] font-semibold text-[var(--muted-2)] uppercase tracking-wider mt-2">
                <Command.Item onSelect={() => runCommand(() => router.push('/decisions/1'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <CheckCircle2 className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Approve all clean filings</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/reconcile/cl-1'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <Play className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Run reconciliation</span>
                </Command.Item>
                <Command.Item onSelect={() => runCommand(() => router.push('/documents'))} className="flex items-center px-2.5 py-2.5 rounded-[6px] text-[13px] font-medium text-[var(--text)] cursor-pointer aria-selected:bg-[var(--royal)]/10 aria-selected:text-[var(--royal)] outline-none group transition-colors">
                  <FileText className="w-4 h-4 mr-3 text-[var(--muted)] group-aria-selected:text-[var(--royal)]" strokeWidth={1.5} />
                  <span className="flex-1">Review documents</span>
                </Command.Item>
              </Command.Group>
            )}

          </Command.List>
        </Command>
      </div>
    </div>
  );
}
