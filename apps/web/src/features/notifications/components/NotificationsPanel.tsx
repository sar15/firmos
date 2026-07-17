"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { EmptyState } from "@/components/EmptyState";
import { MonoValue } from "@/components/MonoValue";
import { StatusDot } from "@/components/StatusDot";
import { AppNotification } from "../notifications.api";
import { useNotifications } from "../useNotifications";

interface NotificationsPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

export const NotificationsPanel = ({ isOpen, onClose }: NotificationsPanelProps) => {
  const router = useRouter();
  const panelRef = useRef<HTMLDivElement>(null);
  const { notifications, error, isLoading, reload, markEveryNotificationRead, markNotificationRead } = useNotifications(isOpen);

  useEffect(() => {
    const closeOnOutsidePointer = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (!panelRef.current?.contains(target) && !target.closest("[data-notifications-trigger]")) onClose();
    };

    if (isOpen) document.addEventListener("mousedown", closeOnOutsidePointer);
    return () => document.removeEventListener("mousedown", closeOnOutsidePointer);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const needsYou = notifications.filter(notification => notification.group === "NEEDS_YOU");
  const updates = notifications.filter(notification => notification.group === "UPDATES");
  const openNotification = async (notification: AppNotification) => {
    if (!notification.isRead) await markNotificationRead(notification.id);
    onClose();
    router.push(notification.actionUrl);
  };
  const renderNotification = (notification: AppNotification) => (
    <button key={notification.id} type="button" onClick={() => void openNotification(notification)} className="relative flex w-full flex-col border-b border-[var(--hairline)] px-4 py-3 text-left transition-colors last:border-none hover:bg-[var(--hover)] focus-ring">
      <span className="flex items-start justify-between gap-4"><span className="flex flex-col gap-1 pr-6"><span className="text-[13px] font-medium leading-tight text-[var(--text)]">{notification.title}</span><span className="truncate text-[12px] text-[var(--muted)]">{notification.clientName}</span><span className="mt-0.5 text-[11px] text-[var(--muted-2)]"><MonoValue>{notification.timestamp}</MonoValue></span></span><span className="mt-1 shrink-0"><StatusDot color={notification.urgency} /></span></span>
      {!notification.isRead && <span className="absolute left-1.5 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-[var(--royal)]" aria-label="Unread" />}
    </button>
  );
  const renderGroup = (label: string, items: AppNotification[]) => items.length > 0 && <section><h2 className="sticky top-0 z-10 border-y border-[var(--hairline)] bg-[var(--canvas)] px-4 py-1.5 text-[11px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</h2>{items.map(renderNotification)}</section>;

  return (
    <div ref={panelRef} className="absolute right-0 top-[44px] z-50 flex w-[min(360px,calc(100vw-2rem))] flex-col overflow-hidden rounded-[10px] border border-[var(--hairline)] bg-white shadow-[0_4px_24px_rgba(0,0,0,0.08)]" role="dialog" aria-label="Notifications">
      <div className="flex items-center justify-between border-b border-[var(--hairline)] bg-[var(--canvas)] px-4 py-3"><span className="text-[13px] font-semibold text-[var(--text)]">Notifications</span><button type="button" onClick={() => void markEveryNotificationRead()} className="min-h-11 px-2 text-[11px] font-medium text-[var(--royal)] hover:underline">Mark all read</button></div>
      <div className="max-h-[400px] flex-1 overflow-y-auto">
        {error ? <div className="p-4" role="alert"><p className="text-sm text-[var(--red)]">{error}</p><button type="button" onClick={() => void reload()} className="mt-3 min-h-11 rounded-[6px] border border-[var(--red-border)] px-3 text-sm font-medium text-[var(--red)]">Try again</button></div> : isLoading ? <p className="p-4 text-sm text-[var(--muted)]" role="status">Loading notifications…</p> : notifications.length === 0 ? <div className="flex items-center justify-center p-8"><EmptyState icon={CheckCircle2} title="You’re all caught up" description="No new notifications at this time." /></div> : <div>{renderGroup("Needs you", needsYou)}{renderGroup("Updates", updates)}</div>}
      </div>
    </div>
  );
};
