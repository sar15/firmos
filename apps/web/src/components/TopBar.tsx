"use client";

import React, { useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { NotificationsPanel } from "@/features/notifications/components/NotificationsPanel";
import { FirmSelector } from "@/features/firms/FirmSelector";
import { usePathname } from "next/navigation";

export function TopBar() {
  const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
  const [timestamp, setTimestamp] = useState("");
  const pathname = usePathname();

  useEffect(() => {
    const now = new Date();
    const date = now.toLocaleDateString("en-US", { weekday: "short", day: "numeric", month: "short" });
    const time = now.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
    setTimestamp(`${date}, ${time}`);
  }, []);
  
  // Map pathname to view name
  let viewName = "Agent";
  if (pathname?.startsWith("/clients")) viewName = "Clients";
  if (pathname?.startsWith("/documents")) viewName = "Documents";
  if (pathname?.startsWith("/connectors")) viewName = "Connectors";
  if (pathname?.startsWith("/audit")) viewName = "Audit Log";
  
  const openCommandPalette = () => {
    window.dispatchEvent(new Event("open-command-palette"));
  };

  return (
    <header className="h-[56px] w-full bg-[var(--canvas)] border-b border-[var(--hairline)] flex items-center gap-[12px] px-[22px] shrink-0 z-10 sticky top-0 select-none">
      
      {/* Crumb */}
      <span className="text-[13.5px] text-[var(--muted)] font-medium whitespace-nowrap ml-1">
        <b className="text-[var(--text)] font-semibold">{viewName}</b> &middot; {timestamp || "Loading…"}
      </span>
      
      {/* Spacer to push everything else to the right */}
      <div className="flex-1"></div>

      <FirmSelector />

      {/* Notifications */}
      <div className="relative">
        <button
          data-notifications-trigger
          onClick={(e) => {
            e.stopPropagation();
            setIsNotificationsOpen((prev) => !prev);
          }}
          className="w-[36px] h-[36px] rounded-[10px] border-none bg-transparent text-[var(--muted)] flex items-center justify-center transition-all duration-120 ease-out hover:bg-[var(--hover)] hover:text-[var(--text)] relative"
        >
          <Bell className="w-[15px] h-[15px]" strokeWidth={2} />
        </button>
        <NotificationsPanel 
          isOpen={isNotificationsOpen} 
          onClose={() => setIsNotificationsOpen(false)} 
        />
      </div>
      
      {/* Ask firmOS Command Button */}
      <button
        type="button"
        onClick={openCommandPalette}
        className="ml-2 flex items-center gap-[10px] bg-[var(--panel)] border border-[var(--hairline)] py-2 px-[14px] rounded-[10px] text-[13.5px] text-[var(--muted)] min-w-[240px] transition-all hover:border-[var(--royal-tint-2)] hover:bg-[var(--raised)] hover:text-[var(--text)] hover:shadow-[var(--shadow-xs)] cursor-pointer group"
      >
        <span>Ask firmOS...</span>
        <span className="ml-auto font-mono text-[11px] bg-[var(--canvas)] border border-[var(--hairline)] px-1.5 py-0.5 rounded-[4px] text-[var(--muted)] font-medium group-hover:border-[var(--hairline-2)] transition-colors">
          ⌘K
        </span>
      </button>
      
    </header>
  );
}
