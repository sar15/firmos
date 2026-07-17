"use client";

import { useCallback, useEffect, useState } from "react";
import { AppNotification, listNotifications, markAllRead, markRead } from "./notifications.api";

export const useNotifications = (isOpen: boolean) => {
  const [notifications, setNotifications] = useState<AppNotification[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setNotifications(await listNotifications());
    } catch {
      setError("Notifications could not be loaded. Try again.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) void reload();
  }, [isOpen, reload]);

  const markEveryNotificationRead = useCallback(async () => {
    try {
      await markAllRead();
      await reload();
    } catch {
      setError("Notifications could not be updated. Try again.");
    }
  }, [reload]);

  const markNotificationRead = useCallback(async (id: string) => {
    try {
      await markRead(id);
    } catch {
      setError("Notification could not be updated. Try again.");
    }
  }, []);

  return { notifications, error, isLoading, reload, markEveryNotificationRead, markNotificationRead };
};
