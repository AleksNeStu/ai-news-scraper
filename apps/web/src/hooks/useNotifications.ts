"use client";

/**
 * React hooks for in-app notifications.
 *
 * `useNotifications` polls every 30s while the page is visible. Polling pauses
 * on `document.hidden` to avoid wasted bandwidth on background tabs.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  getUnreadCount,
  listNotifications,
  markNotificationRead,
  type ListNotificationsOpts,
} from "@/lib/api/notifications";
import type { Notification } from "@ai-news-scraper/shared";

const POLL_INTERVAL_MS = 30_000;

export function useNotifications(opts: ListNotificationsOpts = {}) {
  const [data, setData] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const fetch = useCallback(async () => {
    try {
      const list = await listNotifications(optsRef.current);
      setData(list);
      setError(null);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Failed to load notifications");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetch();
    let timer: ReturnType<typeof setInterval> | null = null;

    function start() {
      if (timer) return;
      timer = setInterval(() => void fetch(), POLL_INTERVAL_MS);
    }
    function stop() {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    }

    const onVisibility = () => {
      if (typeof document === "undefined") return;
      if (document.hidden) {
        stop();
      } else {
        void fetch();
        start();
      }
    };

    if (typeof document !== "undefined" && !document.hidden) start();
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", onVisibility);
    }
    return () => {
      stop();
      if (typeof document !== "undefined") {
        document.removeEventListener("visibilitychange", onVisibility);
      }
    };
  }, [fetch]);

  const markRead = useCallback(async (id: string) => {
    // Optimistic update — clear the item locally before the network round-trip.
    setData((prev) => (prev ? prev.filter((n) => n.id !== id) : prev));
    try {
      await markNotificationRead(id);
    } catch {
      // On error, re-fetch to restore the truth.
      void fetch();
    }
  }, [fetch]);

  return { data, loading, error, refetch: fetch, markRead };
}

export function useUnreadCount() {
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    try {
      const c = await getUnreadCount();
      setCount(c);
      setError(null);
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Failed to load count");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetch();
    const id = setInterval(() => void fetch(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetch]);

  return { count, loading, error, refetch: fetch };
}
