"use client";

import React, { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { AppNotification, listNotifications, markRead, markAllRead } from "@/features/notifications/notifications.api";
import { EmptyState } from "@/components/EmptyState";
import { MonoValue } from "@/components/MonoValue";
import { StatusDot } from "@/components/StatusDot";
import { cn } from "@/lib/utils";

interface NotificationsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export function NotificationsPanel({ isOpen, onClose }: NotificationsPanelProps) {
  const router = useRouter();
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      listNotifications().then(setNotifications);
    }
  }, [isOpen]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        // We only close if they didn't click the bell button itself
        // But since the bell button is outside this component, it might conflict.
        // We can check if the click target has a specific class or let the parent handle the bell click by preventing propagation.
        onClose();
      }
    };
    
    if (isOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isOpen, onClose]);

  const handleMarkAllRead = async () => {
    await markAllRead();
    const updated = await listNotifications();
    setNotifications(updated);
  };

  const handleNotificationClick = async (notif: AppNotification) => {
    if (!notif.isRead) {
      await markRead(notif.id);
    }
    onClose();
    router.push(notif.actionUrl);
  };

  if (!isOpen) return null;

  const needsYou = notifications.filter(n => n.group === "NEEDS_YOU");
  const updates = notifications.filter(n => n.group === "UPDATES");

  const renderNotification = (n: AppNotification) => (
    <div 
      key={n.id}
      onClick={() => handleNotificationClick(n)}
      className="flex flex-col py-3 px-4 border-b border-[var(--hairline)] hover:bg-[var(--hover)] cursor-pointer transition-colors last:border-none relative group"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex flex-col gap-1 pr-6">
          <span className={cn("text-[13px] font-medium leading-tight", !n.isRead ? "text-[var(--text)]" : "text-[var(--text)]")}>
            {n.title}
          </span>
          <span className="text-[12px] text-[var(--muted)] truncate">{n.clientName}</span>
          <span className="text-[11px] text-[var(--muted-2)] mt-0.5"><MonoValue>{n.timestamp}</MonoValue></span>
        </div>
        <div className="mt-1 shrink-0">
          <StatusDot color={n.urgency} />
        </div>
      </div>
      {!n.isRead && (
        <div className="absolute left-1.5 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-[var(--royal)]"></div>
      )}
    </div>
  );

  return (
    <div 
      ref={panelRef}
      className="absolute top-[44px] right-0 w-[360px] bg-white border border-[var(--hairline)] rounded-[8px] shadow-[0_4px_24px_rgba(0,0,0,0.08)] flex flex-col z-50 overflow-hidden"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--hairline)] bg-[var(--canvas)]">
        <span className="text-[13px] font-semibold text-[var(--text)]">Notifications</span>
        <button 
          onClick={handleMarkAllRead}
          className="text-[11px] font-medium text-[var(--royal)] hover:underline"
        >
          Mark all read
        </button>
      </div>

      <div className="flex-1 max-h-[400px] overflow-y-auto">
        {notifications.length === 0 ? (
          <div className="p-8 flex items-center justify-center">
            <EmptyState icon={CheckCircle2} title="You're all caught up" description="No new notifications at this time." />
          </div>
        ) : (
          <div className="flex flex-col">
            {needsYou.length > 0 && (
              <div className="flex flex-col">
                <div className="px-4 py-1.5 bg-[var(--canvas)] border-y border-[var(--hairline)] text-[11px] font-bold text-[var(--muted)] uppercase tracking-wider sticky top-0 z-10">
                  Needs you
                </div>
                <div className="flex flex-col">
                  {needsYou.map(renderNotification)}
                </div>
              </div>
            )}
            
            {updates.length > 0 && (
              <div className="flex flex-col">
                <div className="px-4 py-1.5 bg-[var(--canvas)] border-y border-[var(--hairline)] text-[11px] font-bold text-[var(--muted)] uppercase tracking-wider sticky top-0 z-10">
                  Updates
                </div>
                <div className="flex flex-col">
                  {updates.map(renderNotification)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
