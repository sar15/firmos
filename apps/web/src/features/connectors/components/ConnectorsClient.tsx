"use client";

import { useState, useEffect } from "react";
import { Search, MoreHorizontal, Check, Loader2, Link2Off, SearchX, CircleAlert } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { ConnectorDrawer } from "./ConnectorDrawer";
import { Category, isConnected } from "@/types";
import { Connector } from "@/types";
import { getConnectors, getSetupReadiness, getZohoOrganizationChoice, selectZohoOrganization, SetupReadiness, ZohoOrganizationChoice } from "../connectors.api";

import { PageHeader } from "@/components/PageHeader";
import { ConnectorOperations } from "./ConnectorOperations";
import { listClients } from "@/features/clients/clients.api";

export function ConnectorsClient() {
  const [activeTab, setActiveTab] = useState<"browse" | "connected">("browse");
  const [searchQuery, setSearchQuery] = useState("");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState<Connector | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<SetupReadiness | null>(null);
  const [zohoChoice, setZohoChoice] = useState<ZohoOrganizationChoice | null>(null);
  const [selectedOrganizationId, setSelectedOrganizationId] = useState("");
  const [clients, setClients] = useState<{ id: string; legalName: string }[]>([]);
  const [selectedClientId, setSelectedClientId] = useState("");
  const [zohoError, setZohoError] = useState<string | null>(null);
  const [connectingZoho, setConnectingZoho] = useState(false);

  useEffect(() => {
    getConnectors()
      .then(setCategories)
      .catch(() => setError("Connectors could not be loaded. Please retry."))
      .finally(() => setLoading(false));
    getSetupReadiness().then(setReadiness).catch(() => setReadiness(null));
  }, []);

  useEffect(() => {
    const attemptId = new URLSearchParams(window.location.search).get("zoho_attempt");
    if (!attemptId) return;
    Promise.all([getZohoOrganizationChoice(attemptId), listClients()])
      .then(async ([choice, clientRows]) => {
        if (choice.organizations.length === 1 && clientRows.length === 1) {
          setConnectingZoho(true);
          await selectZohoOrganization(choice.attempt_id, choice.organizations[0].organization_id, clientRows[0].id);
          window.history.replaceState({}, "", "/connectors");
          setCategories(await getConnectors());
          setActiveTab("connected");
          return;
        }
        setZohoChoice(choice);
        setSelectedOrganizationId(choice.organizations[0]?.organization_id ?? "");
        setClients(clientRows);
        setSelectedClientId(clientRows[0]?.id ?? "");
      })
      .catch((reason: Error) => setZohoError(reason.message))
      .finally(() => setConnectingZoho(false));
  }, []);

  const confirmZohoOrganization = async () => {
    if (!zohoChoice || !selectedOrganizationId || !selectedClientId) return;
    setConnectingZoho(true);
    setZohoError(null);
    try {
      await selectZohoOrganization(zohoChoice.attempt_id, selectedOrganizationId, selectedClientId);
      setZohoChoice(null);
      window.history.replaceState({}, "", "/connectors");
      setCategories(await getConnectors());
      setActiveTab("connected");
    } catch (reason) {
      setZohoError(reason instanceof Error ? reason.message : "Zoho could not be connected.");
    } finally {
      setConnectingZoho(false);
    }
  };

  const handleOpenDrawer = (connector: Connector) => {
    setSelectedConnector(connector);
    setDrawerOpen(true);
  };

  const allConnected = categories.flatMap(c => c.items).filter(isConnected);
  const connectedCount = allConnected.length;
  const needsAttentionCount = allConnected.filter(item => item.status === "NEEDS_ATTENTION").length;

  return (
    <div className="w-full h-full flex flex-col bg-white">
      
      <PageHeader 
        title="Connectors"
        className="bg-white pt-10 px-8 shrink-0 flex justify-center"
        contentClassName="max-w-[860px]"
        meta={
          <div className="flex items-center gap-3">
            <div className="relative">
              <Search className="w-4 h-4 text-muted-2 absolute left-3 top-1/2 -translate-y-1/2" strokeWidth={1.5} />
              <input 
                type="text" 
                placeholder="Search connectors..." 
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-[320px] h-8 pl-9 pr-3 border border-hairline rounded-[6px] text-[13px] bg-hover focus:bg-white transition-all duration-150 outline-none focus:border-[var(--royal)]/50"
              />
            </div>
          </div>
        }
      >
        <div className="flex gap-6 w-full pt-2">
          <button 
            onClick={() => setActiveTab("browse")}
            className={`pb-2.5 text-[13px] font-medium transition-all duration-150 ${activeTab === "browse" ? "text-text border-b-2 border-[var(--royal)]" : "text-muted border-b-2 border-transparent hover:text-text"}`}
          >
            Browse
          </button>
          <button 
            onClick={() => setActiveTab("connected")}
            className={`pb-2.5 text-[13px] font-medium flex items-center gap-2 transition-all duration-150 ${activeTab === "connected" ? "text-text border-b-2 border-[var(--royal)]" : "text-muted border-b-2 border-transparent hover:text-text"}`}
          >
            Connected
            <span className="px-1.5 py-0.5 rounded-[4px] bg-hover border border-hairline text-[11px] mono">
              {connectedCount}
            </span>
          </button>
        </div>
      </PageHeader>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 overflow-y-auto w-full flex justify-center py-6 px-8">
        <div className="w-full max-w-[860px] flex flex-col">
          <ConnectorOperations />
          {connectingZoho && !zohoChoice && <p className="mb-6 flex items-center gap-2 text-sm text-[var(--muted)]"><Loader2 className="h-4 w-4 animate-spin" />Finishing your Zoho Books connection…</p>}
          {zohoChoice && <section className="mb-6 rounded-lg border border-[var(--royal)]/25 bg-[var(--royal-tint)] p-5" aria-label="Choose Zoho Books organization">
            <p className="text-sm font-semibold text-[var(--text)]">Choose the Zoho Books organization to connect</p>
            <p className="mt-1 text-sm text-[var(--muted)]">firmOS will read registers from this organization. Nothing is created in Zoho until you approve a specific action.</p>
            <label className="mt-4 block text-xs font-medium text-[var(--text)]" htmlFor="zoho-organization">Organization</label>
            <select id="zoho-organization" value={selectedOrganizationId} onChange={(event) => setSelectedOrganizationId(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-[var(--hairline)] bg-white px-3 text-sm text-[var(--text)]">
              {zohoChoice.organizations.map((organization) => <option key={organization.organization_id} value={organization.organization_id}>{organization.name}</option>)}
            </select>
            <label className="mt-3 block text-xs font-medium text-[var(--text)]" htmlFor="zoho-client">FirmOS client</label>
            <select id="zoho-client" value={selectedClientId} onChange={(event) => setSelectedClientId(event.target.value)} className="mt-1 h-10 w-full rounded-md border border-[var(--hairline)] bg-white px-3 text-sm text-[var(--text)]">
              {clients.map((client) => <option key={client.id} value={client.id}>{client.legalName}</option>)}
            </select>
            {zohoError && <p className="mt-3 text-sm text-[var(--red)]">{zohoError}</p>}
            <div className="mt-4 flex justify-end"><button onClick={confirmZohoOrganization} disabled={connectingZoho || !selectedOrganizationId || !selectedClientId} className="inline-flex h-9 items-center gap-2 rounded-md bg-[var(--royal)] px-3 text-sm font-medium text-white disabled:opacity-50">{connectingZoho && <Loader2 className="h-4 w-4 animate-spin" />}Connect Zoho Books</button></div>
          </section>}
          {zohoError && !zohoChoice && <div className="mb-6 rounded-md border border-[var(--red-border)] bg-[var(--red-tint)] p-4 text-sm text-[var(--red)]">{zohoError}</div>}
          
          {loading ? (
            <div className="flex justify-center p-10">
              <Loader2 className="w-6 h-6 text-muted-2 animate-spin" />
            </div>
          ) : error ? <div className="rounded-md border border-[var(--red-border)] bg-[var(--red-tint)] p-4 text-sm text-[var(--red)]">{error}</div> : activeTab === "browse" ? (
            <div className="flex flex-col gap-8">
              {readiness && <section className="rounded-lg border border-[var(--hairline)] bg-[var(--hover)] p-4" aria-label="Setup readiness">
                <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-[var(--text)]">Setup readiness</p><p className="mt-1 text-sm text-[var(--muted)]">{readiness.production_ready ? "Core production checks pass." : "Finish these checks before relying on automation."}</p></div>{readiness.production_ready ? <span className="inline-flex items-center gap-1 rounded bg-[var(--royal-tint)] px-2 py-1 text-xs font-medium text-[var(--royal)]"><Check className="h-3.5 w-3.5" />Ready</span> : <CircleAlert className="h-5 w-5 shrink-0 text-[var(--amber)]" />}</div>
                <ul className="mt-4 grid gap-2 sm:grid-cols-2">{readiness.checks.filter(check => !check.ready).map(check => <li key={check.id} className="rounded-md border border-[var(--hairline)] bg-white px-3 py-2 text-sm"><p className="font-medium text-[var(--text)]">{check.label}</p>{check.detail && <p className="mt-1 text-xs leading-5 text-[var(--muted)]">{check.detail}</p>}</li>)}</ul>
              </section>}
              {categories.every(c => c.items.filter(item => item.name.toLowerCase().includes(searchQuery.toLowerCase()) || item.description.toLowerCase().includes(searchQuery.toLowerCase())).length === 0) ? (
                <EmptyState 
                  icon={SearchX} 
                  title="No connectors found" 
                  description="We couldn't find any connectors matching your search." 
                />
              ) : (
                categories.map((category) => {
                  const filteredItems = category.items.filter(item => item.name.toLowerCase().includes(searchQuery.toLowerCase()) || item.description.toLowerCase().includes(searchQuery.toLowerCase()));
                  if (filteredItems.length === 0) return null;
  
                  return (
                    <div key={category.title} className="flex flex-col">
                      <div className="flex items-center justify-between mb-2">
                        <h2 className="text-[11px] font-semibold text-[var(--muted-2)] uppercase tracking-widest">{category.title}</h2>
                        {category.caption && <span className="text-[11px] text-[var(--muted-2)]">{category.caption}</span>}
                      </div>
                      <div className="flex flex-col border-t border-[var(--hairline)]">
                        {filteredItems.map(item => (
                          <div 
                            key={item.id} 
                            onClick={() => handleOpenDrawer(item)}
                            className="flex items-center justify-between py-2 border-b border-[var(--hairline)] hover:bg-[var(--hover)] transition-all duration-150 cursor-pointer group px-2 -mx-2 rounded-[6px]"
                          >
                            <div className="flex items-center gap-4">
                              <div className="w-8 h-8 bg-[var(--hover)] border border-[var(--hairline)] rounded-[6px] flex items-center justify-center shrink-0">
                                <span className="font-semibold text-[var(--text)] text-[13px]">{item.name.charAt(0)}</span>
                              </div>
                              <div className="flex items-center gap-3 min-w-0 pr-4">
                                <span className="text-[13px] font-medium text-[var(--text)] truncate w-[160px]">{item.name}</span>
                                <span className="text-[12px] text-[var(--muted)] truncate">{item.description}</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-3 shrink-0">
                              {isConnected(item) ? (
                                <>
                                  <div className="flex items-center gap-1.5 px-2 py-0.5 bg-[var(--royal-tint)] text-[var(--royal)] border border-[var(--royal)]/20 rounded-[4px] text-[11px] font-medium">
                                    <Check className="w-3 h-3" strokeWidth={1.5} />
                                    Connected
                                  </div>
                                  <button disabled title="Connector actions are not available yet" className="cursor-not-allowed p-1 text-[var(--muted-2)] opacity-50">
                                    <MoreHorizontal className="w-4 h-4" strokeWidth={1.5} />
                                  </button>
                                </>
                              ) : (
                                <button onClick={(event) => { event.stopPropagation(); handleOpenDrawer(item); }} className="h-9 px-3 bg-white border border-[var(--hairline)] rounded-[6px] text-[12px] font-medium text-[var(--text)] hover:bg-[var(--hover)] transition-all duration-150 cursor-pointer">
                                  Connect
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          ) : (
            <div className="flex flex-col w-full">
              {/* Summary Strip */}
              <div className="flex items-center gap-4 py-2 mb-4">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-text" />
                  <span className="text-[12px] font-medium text-text mono">{connectedCount} connected</span>
                </div>
                <div className="w-[1px] h-3 bg-hairline" />
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-royal" />
                  <span className="text-[12px] font-medium text-text mono">{connectedCount - needsAttentionCount} healthy</span>
                </div>
                <div className="w-[1px] h-3 bg-hairline" />
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-amber" />
                  <span className="text-[12px] font-medium text-text mono">{needsAttentionCount} need attention</span>
                </div>
              </div>

              {/* List */}
              <div className="flex flex-col border-t border-[var(--hairline)]">
                {allConnected.length === 0 ? (
                  <div className="mt-8">
                    <EmptyState 
                      icon={Link2Off} 
                      title="No active connections" 
                      description="You haven't connected any apps to firmOS yet." 
                    />
                  </div>
                ) : (
                  allConnected.map((item) => (
                    <div key={item.id} className="flex items-center justify-between py-2 border-b border-[var(--hairline)] hover:bg-[var(--hover)] transition-all duration-150 px-2 -mx-2 rounded-[6px] group">
                      <div className="flex items-center gap-4">
                        <div className="w-8 h-8 bg-[var(--hover)] border border-[var(--hairline)] rounded-[6px] flex items-center justify-center shrink-0">
                          <span className="font-semibold text-[var(--text)] text-[13px]">{item.name.charAt(0)}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-[13px] font-medium text-[var(--text)] w-[160px]">{item.name}</span>
                          <div className="flex items-center">
                            {item.status === "NEEDS_ATTENTION" ? (
                              <span className="text-[12px] text-[var(--amber)] mono font-medium">Needs attention</span>
                            ) : item.lastSyncedAt ? (
                              <span className="text-[12px] text-[var(--royal)] mono">Last synced {new Date(item.lastSyncedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                            ) : (
                              <span className="text-[12px] text-[var(--royal)] mono">Connected</span>
                            )}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button 
                          onClick={() => handleOpenDrawer(item)}
                          className="h-7 px-3 bg-white border border-[var(--hairline)] rounded-[6px] text-[12px] font-medium text-[var(--text)] hover:bg-[var(--hover)] transition-all duration-150 cursor-pointer"
                        >
                          Manage
                        </button>
                        <button disabled title="Connector actions are not available yet" className="cursor-not-allowed p-1 text-[var(--muted-2)] opacity-50">
                          <MoreHorizontal className="w-4 h-4" strokeWidth={1.5} />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}

        </div>
      </div>

      <ConnectorDrawer 
        isOpen={drawerOpen} 
        onClose={() => setDrawerOpen(false)} 
        connectorId={selectedConnector?.id || null}
        connectorName={selectedConnector?.name || null}
        description={selectedConnector?.description || ""}
      />
    </div>
  );
}
