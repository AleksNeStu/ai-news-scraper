"use client";

/**
 * One-click unsubscribe landing page (RFC 8058 §3.2).
 *
 * Public route — no auth. The signed JWT in `?token=` is the credential;
 * `?digest_id=` identifies which digest to flip `email_digest_enabled` for.
 *
 * On mount we auto-submit (no manual click required by the RFC). While the
 * POST is in flight we render a "Working…" state; on completion we show
 * confirmation based on the server's `UnsubscribeResponse`:
 *   - `unsubscribed: true`  → "You've been unsubscribed"
 *   - `unsubscribed: false` → "You were already unsubscribed on {at}"
 *
 * Errors:
 *   - Missing digest_id / token → explain the link is malformed.
 *   - 4xx from backend (expired token, replay) → show the detail message.
 *   - Network / 5xx → "Couldn't reach the server. Try again from the email."
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, MailMinus, AlertTriangle } from "lucide-react";
import { unsubscribeDigest } from "@/lib/api/digest";
import { ApiError } from "@/lib/api";

type Phase =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "ok"; unsubscribed: boolean; at: string }
  | { kind: "error"; message: string };

export default function UnsubscribePage() {
  const search = useSearchParams();
  const digestId = search?.get("digest_id") ?? "";
  const token = search?.get("token") ?? "";
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });

  useEffect(() => {
    if (phase.kind !== "idle") return;
    if (!digestId || !token) {
      setPhase({
        kind: "error",
        message:
          "This unsubscribe link is missing required fields. Please use the link from your email.",
      });
      return;
    }
    setPhase({ kind: "pending" });
    let cancelled = false;
    unsubscribeDigest(digestId, token)
      .then((res) => {
        if (cancelled) return;
        setPhase({ kind: "ok", unsubscribed: res.unsubscribed, at: res.at });
      })
      .catch((e) => {
        if (cancelled) return;
        const msg =
          e instanceof ApiError
            ? e.message
            : "Couldn't reach the server. Try again from the email.";
        setPhase({ kind: "error", message: msg });
      });
    return () => {
      cancelled = true;
    };
  }, [digestId, token, phase.kind]);

  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <MailMinus className="mb-4 h-10 w-10 text-primary" />
        <h1 className="headline-serif text-2xl">Daily brief unsubscribe</h1>

        <div className="mt-8 w-full">
          {phase.kind === "idle" || phase.kind === "pending" ? (
            <p className="text-sm text-muted-foreground">Working on it…</p>
          ) : phase.kind === "ok" && phase.unsubscribed ? (
            <SuccessCard
              title="You've been unsubscribed"
              body="No more daily briefs will be emailed to you. You can still view them in the dashboard."
              at={phase.at}
            />
          ) : phase.kind === "ok" && !phase.unsubscribed ? (
            <SuccessCard
              title="You were already unsubscribed"
              at={phase.at}
              body="No further action needed — the link in your email is still valid, but your preference is already set."
            />
          ) : (
            <ErrorCard message={phase.message} />
          )}
        </div>

        <Link
          href="/login"
          className="mt-10 text-sm text-muted-foreground hover:text-primary"
        >
          Back to AI News Search →
        </Link>
      </div>
    </main>
  );
}

function SuccessCard({
  title,
  body,
  at,
}: {
  title: string;
  body?: string;
  at: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-canvas p-6">
      <CheckCircle2 className="mx-auto mb-3 h-6 w-6 text-success" />
      <h2 className="font-medium">{title}</h2>
      {body && <p className="mt-1 text-sm text-muted-foreground">{body}</p>}
      <p className="mt-3 text-xs text-muted-foreground">
        Confirmed at {formatTimestamp(at)}.
      </p>
    </div>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-canvas p-6">
      <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-destructive" />
      <h2 className="font-medium">Couldn't unsubscribe</h2>
      <p className="mt-1 text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

function formatTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
