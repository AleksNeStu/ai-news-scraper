import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import * as apiMod from "@/lib/api/notifications";
import { useNotifications, useUnreadCount } from "@/hooks/useNotifications";
import type { Notification } from "@ai-news-scraper/shared";

const makeNotification = (over: Partial<Notification> = {}): Notification => ({
  id: "n1",
  user_id: "u1",
  kind: "brief_ready",
  title: "Today's brief is ready",
  preview: "Cluster summary...",
  href: "/dashboard/brief/2026-06-29",
  digest_id: "d1",
  read: false,
  created_at: "2026-06-29T08:00:00Z",
  read_at: null,
  ...over,
});

describe("useNotifications", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches on mount and exposes the list", async () => {
    const listSpy = vi.spyOn(apiMod, "listNotifications").mockResolvedValue([makeNotification()]);
    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(listSpy).toHaveBeenCalled();
    expect(result.current.data).toHaveLength(1);
    expect(result.current.error).toBeNull();
  });

  it("polls every 30 seconds", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const listSpy = vi.spyOn(apiMod, "listNotifications").mockResolvedValue([]);
    renderHook(() => useNotifications({ limit: 10 }));
    await waitFor(() => expect(listSpy).toHaveBeenCalledTimes(1));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(listSpy).toHaveBeenCalledTimes(2);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(listSpy).toHaveBeenCalledTimes(3);
  });

  it("markRead optimistically removes the notification and calls the API", async () => {
    const initial = [makeNotification({ id: "a" }), makeNotification({ id: "b" })];
    const readSpy = vi.spyOn(apiMod, "markNotificationRead").mockResolvedValue();
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue(initial);

    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.data).toHaveLength(2));

    await act(async () => {
      await result.current.markRead("a");
    });

    expect(readSpy).toHaveBeenCalledWith("a");
    expect(result.current.data.map((n) => n.id)).toEqual(["b"]);
  });

  it("recovers state when markRead fails", async () => {
    const initial = [makeNotification({ id: "a" })];
    const refetchSpy = vi.spyOn(apiMod, "listNotifications").mockResolvedValue(initial);
    vi.spyOn(apiMod, "markNotificationRead").mockRejectedValue(new Error("boom"));

    const { result } = renderHook(() => useNotifications());
    await waitFor(() => expect(result.current.data).toHaveLength(1));

    await act(async () => {
      await result.current.markRead("a");
    });

    expect(refetchSpy.mock.calls.length).toBeGreaterThanOrEqual(2); // initial + recovery
  });
});

describe("useUnreadCount", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("returns the count from the API", async () => {
    vi.spyOn(apiMod, "getUnreadCount").mockResolvedValue(7);
    const { result } = renderHook(() => useUnreadCount());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.count).toBe(7);
  });
});
