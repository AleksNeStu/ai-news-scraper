import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NotificationBell } from "@/components/NotificationBell";
import * as apiMod from "@/lib/api/notifications";
import type { Notification } from "@ai-news-scraper/shared";

const makeNotification = (over: Partial<Notification> = {}): Notification => ({
  id: "n1",
  user_id: "u1",
  kind: "brief_ready",
  title: "Today's brief is ready",
  preview: "Cluster summary preview...",
  href: "/dashboard/brief/2026-06-29",
  digest_id: "d1",
  read: false,
  created_at: "2026-06-29T08:00:00Z",
  read_at: null,
  ...over,
});

describe("NotificationBell", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    // jsdom defaults `document.hidden = false` so polling starts — fine for tests.
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders the unread count badge with an updated aria-label", async () => {
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue([
      makeNotification({ id: "1" }),
      makeNotification({ id: "2" }),
      makeNotification({ id: "3", read: true }),
    ]);

    render(<NotificationBell />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Notifications, 2 unread/i })).toBeInTheDocument();
    });
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("does not show a badge when there are no unread notifications", async () => {
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue([]);

    render(<NotificationBell />);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Notifications, 0 unread/i })).toBeInTheDocument();
    });
    expect(screen.queryByText(/^\d+$/)).not.toBeInTheDocument();
  });

  it("clicking the bell toggles the dropdown open and closed", async () => {
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue([
      makeNotification({ id: "1", title: "Brief ready" }),
    ]);

    render(<NotificationBell />);
    const btn = await screen.findByRole("button", { name: /Notifications/ });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    fireEvent.click(btn);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(screen.getByText("Brief ready")).toBeInTheDocument();

    fireEvent.click(btn);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("clicking a notification calls markNotificationRead and closes the dropdown", async () => {
    const readSpy = vi.spyOn(apiMod, "markNotificationRead").mockResolvedValue();
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue([
      makeNotification({ id: "n1", title: "First" }),
      makeNotification({ id: "n2", title: "Second" }),
    ]);

    render(<NotificationBell />);
    const bell = await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(bell);

    const firstLink = await screen.findByRole("menuitem", { name: /First/ });
    fireEvent.click(firstLink);

    await waitFor(() => expect(readSpy).toHaveBeenCalledWith("n1"));
    // Clicking a notification closes the dropdown (navigates in the real browser).
    await waitFor(() => expect(screen.queryByRole("menu")).not.toBeInTheDocument());
    // The badge count is now 1 unread (only "Second" remains).
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /Notifications, 1 unread/i })).toBeInTheDocument(),
    );
  });

  it("closes the dropdown when Escape is pressed", async () => {
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue([makeNotification()]);
    render(<NotificationBell />);
    const btn = await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(btn);
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no notifications", async () => {
    vi.spyOn(apiMod, "listNotifications").mockResolvedValue([]);
    render(<NotificationBell />);
    const btn = await screen.findByRole("button", { name: /Notifications/ });
    fireEvent.click(btn);
    expect(screen.getByText("No new notifications")).toBeInTheDocument();
  });
});
