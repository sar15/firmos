import { getAuthHeaders } from "@/lib/auth";

export type NotificationGroup = "NEEDS_YOU" | "UPDATES";

export interface AppNotification {
  id: string;
  group: NotificationGroup;
  title: string;
  clientName: string;
  timestamp: string; // ISO or relative
  isRead: boolean;
  actionUrl: string; // e.g. "/decisions/dec-1"
  urgency: "red" | "amber" | "royal";
}

export async function listNotifications(): Promise<AppNotification[]> {
  const res = await fetch("/api/notifications", { headers: await getAuthHeaders() });
  if (!res.ok) throw new Error(`Failed to list notifications: ${res.statusText}`);
  return res.json();
}

export async function markRead(id: string): Promise<void> {
  const res = await fetch(`/api/notifications/${id}/read`, {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to mark read: ${res.statusText}`);
}

export async function markAllRead(): Promise<void> {
  const res = await fetch("/api/notifications/read-all", {
    method: "POST",
    headers: await getAuthHeaders(),
  });
  if (!res.ok) throw new Error(`Failed to mark all read: ${res.statusText}`);
}
