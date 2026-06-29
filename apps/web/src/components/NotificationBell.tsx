"use client";

/**
 * Top-right header bell. Shows unread count badge and a dropdown of the 10
 * most recent notifications. Click outside / `Escape` closes the dropdown.
 *
 * Accessibility:
 *   - `aria-label` updates with the unread count.
 *   - Dropdown items are real `<button>` / `<a>` (keyboard-focusable).
 *   - First item is auto-focused on open for screen-reader handoff.
 */

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Bell } from "lucide-react";
import { useNotifications } from "@/hooks/useNotifications";
import type { Notification } from "@ai-news-scraper/shared";
import { cn } from "@/lib/utils";

const DROPDOWN_LIMIT = 10;

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const firstItemRef = useRef<HTMLAnchorElement | HTMLButtonElement | null>(null);

  const { data, markRead } = useNotifications({ limit: DROPDOWN_LIMIT });
  // Unread count derived from the polled list (the server returns up to 50,
  // so `unread` here is an accurate count for the dropdown window).
  const unread = data.filter((n) => !n.read).length;

  // Close on click outside / Escape.
  useEffect(() => {
    if (!open) return;
    function onDown(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    // Move focus into the dropdown on open.
    firstItemRef.current?.focus();
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function onItemClick(n: Notification) {
    if (!n.read) void markRead(n.id);
    setOpen(false);
  }

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={`Notifications, ${unread} unread`}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "relative inline-flex h-9 w-9 items-center justify-center rounded-md border border-border bg-surface text-muted-foreground hover:text-foreground hover:border-primary/40",
          open && "border-primary/40 text-foreground",
        )}
      >
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-1 -top-1 min-w-[18px] rounded-full bg-destructive px-1 text-[10px] font-semibold leading-[18px] text-destructive-foreground"
          >
            {unread > 99 ? "99+" : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 z-50 mt-2 w-80 origin-top-right rounded-lg border border-border bg-canvas shadow-lg"
        >
          <div className="border-b border-border px-4 py-2 text-xs uppercase tracking-wider text-muted-foreground">
            Recent notifications
          </div>
          {data.length === 0 ? (
            <p className="px-4 py-6 text-center text-sm text-muted-foreground">No new notifications</p>
          ) : (
            <ul className="max-h-96 overflow-y-auto">
              {data.slice(0, DROPDOWN_LIMIT).map((n, i) => {
                const isFirst = i === 0;
                const body = (
                  <>
                    <div className="flex items-baseline justify-between gap-2">
                      <span className={cn("line-clamp-1 text-sm font-medium", !n.read && "text-foreground")}>
                        {n.title}
                      </span>
                      {!n.read && (
                        <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-primary" />
                      )}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{n.preview}</p>
                  </>
                );
                if (n.href) {
                  return (
                    <li key={n.id}>
                      <Link
                        ref={isFirst ? (firstItemRef as React.RefObject<HTMLAnchorElement>) : undefined}
                        href={n.href}
                        role="menuitem"
                        onClick={() => onItemClick(n)}
                        className="block px-4 py-3 hover:bg-surface focus:bg-surface focus:outline-none"
                      >
                        {body}
                      </Link>
                    </li>
                  );
                }
                return (
                  <li key={n.id}>
                    <button
                      ref={isFirst ? (firstItemRef as React.RefObject<HTMLButtonElement>) : undefined}
                      type="button"
                      role="menuitem"
                      onClick={() => onItemClick(n)}
                      className="block w-full px-4 py-3 text-left hover:bg-surface focus:bg-surface focus:outline-none"
                    >
                      {body}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <div className="border-t border-border px-4 py-2">
            <Link
              href="/dashboard/brief"
              className="text-xs text-primary hover:underline"
              onClick={() => setOpen(false)}
            >
              View all briefs →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
