"use client";

import React, { useRef, useState, useEffect } from "react";
import { FileCheck2, Send } from "lucide-react";
import { listClients } from "@/features/clients/clients.api";
import { Client } from "@/types";
import { sendChatMessage } from "./agent.api";

interface AgentComposerProps {
  client: Client | null;
  period: string;
  onClientSelected: (client: Client) => void;
  onMessageSent?: () => void;
}

export function AgentComposer({ client, period, onClientSelected, onMessageSent }: AgentComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [value, setValue] = useState("");
  const [loading, setLoading] = useState(false);
  
  // @-mention state
  const [showMention, setShowMention] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [value]);

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value;
    setValue(text);

    // Simple @-mention detection
    const match = text.match(/@(\w*)$/);
    if (match) {
      setShowMention(true);
      fetchClients(match[1]);
    } else {
      setShowMention(false);
    }
  };

  const fetchClients = async (query: string) => {
    try {
      const data = await listClients({ search: query });
      setClients(data.slice(0, 5));
    } catch (err) {
      console.error(err);
    }
  };

  const selectMention = (selectedClient: Client) => {
    const newText = value.replace(/@\w*$/, `@${selectedClient.legalName} `);
    setValue(newText);
    setShowMention(false);
    onClientSelected(selectedClient);
    if (textareaRef.current) textareaRef.current.focus();
  };

  const handleSend = async () => {
    if (!value.trim() || loading || !client) return;
    setLoading(true);
    try {
      await sendChatMessage(client.id, period, value.trim());
      setValue("");
      if (onMessageSent) onMessageSent();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-[var(--hairline)] bg-[var(--canvas)] p-3.5 px-8 pb-4.5 shrink-0 z-10 relative">
      <div className="max-w-[760px] mx-auto w-full relative">
        
        {/* @-mention popup */}
        {showMention && clients.length > 0 && (
          <div className="absolute bottom-full mb-2 left-0 w-64 bg-white border border-[var(--hairline)] rounded-[6px] shadow-lg overflow-hidden z-20">
            {clients.map(client => (
              <button
                type="button"
                key={client.id}
                onClick={() => selectMention(client)}
                className="px-3 py-2 text-[13px] hover:bg-[var(--raised)] cursor-pointer text-[var(--text)] border-b border-[var(--hairline)] last:border-0"
              >
                {client.legalName}
              </button>
            ))}
          </div>
        )}

        <div className="bg-[var(--raised)] border border-[var(--hairline-2)] rounded-[16px] p-1.5 transition-all shadow-sm focus-within:border-[var(--royal)] focus-within:shadow-[0_0_0_4px_var(--royal-tint),0_1px_3px_rgba(15,23,42,0.06),0_1px_2px_rgba(15,23,42,0.04)]">
          <textarea 
            ref={textareaRef}
            value={value}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
            placeholder={client ? "Ask about registers, reconciliation, or a reviewed accounting action…" : "Type @ to choose a client first"}
            className="w-full border-none outline-none resize-none px-3.5 py-3 font-sans text-[14.5px] bg-transparent leading-relaxed text-[var(--text)] placeholder:text-[var(--muted-2)] max-h-[200px] overflow-y-auto"
          />
          <div className="flex flex-wrap items-center gap-2 px-2.5 py-1.5 pb-1">
            <button type="button" disabled={!client} onClick={() => { setValue("Prepare the manual GST filing pack for the selected period"); textareaRef.current?.focus(); }} className="text-[12px] text-[var(--muted)] disabled:opacity-50 bg-[var(--panel)] px-3 py-1.5 rounded-full border border-[var(--hairline)] font-medium transition-all flex items-center gap-1.5 hover:text-[var(--royal)] hover:border-[var(--royal-tint-2)] hover:bg-[var(--royal-tint)]">
              <FileCheck2 className="w-3.5 h-3.5" />
              Manual GST pack
            </button>
            <button type="button" disabled={!client} onClick={() => { setValue("Show exceptions in the purchase register"); textareaRef.current?.focus(); }} className="text-[12px] text-[var(--muted)] disabled:opacity-50 bg-[var(--panel)] px-3 py-1.5 rounded-full border border-[var(--hairline)] font-medium transition-all flex items-center gap-1.5 hover:text-[var(--royal)] hover:border-[var(--royal-tint-2)] hover:bg-[var(--royal-tint)]">
              <FileCheck2 className="w-3.5 h-3.5" />
              Purchase exceptions
            </button>
            <button onClick={handleSend} disabled={loading || !value.trim() || !client} className="ml-auto flex items-center gap-1.5 px-3 py-1.5 bg-[var(--royal)] hover:bg-[var(--royal-hover)] disabled:opacity-50 text-white border border-[var(--royal)] rounded-[10px] text-[12.5px] font-medium transition-all hover:-translate-y-px shadow-[0_1px_2px_rgba(37,64,217,0.3),inset_0_1px_0_rgba(255,255,255,0.15)]">
              <Send className="h-3.5 w-3.5" /> {loading ? "Sending..." : "Send"}
            </button>
          </div>
        </div>
        
        <div className="text-[11px] text-[var(--muted-2)] text-center mt-2.5">
          <strong className="text-[var(--muted)] font-medium">firmOS reads, computes, and drafts — you approve.</strong> Tax computed by deterministic engine, never AI. Nothing files without your yes.
        </div>
      </div>
    </div>
  );
}
