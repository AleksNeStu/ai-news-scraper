"use client";

import { useActionState } from "react";
import Link from "next/link";
import { Newspaper } from "lucide-react";
import { loginAction } from "@/lib/auth";

export default function LoginPage() {
  const [state, action, pending] = useActionState(loginAction, { ok: false } as { ok: boolean; error?: string });

  if (state.ok) {
    if (typeof window !== "undefined") window.location.href = "/";
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-canvas p-8">
        <div className="mb-6 flex items-center gap-2">
          <Newspaper className="h-5 w-5 text-primary" />
          <h1 className="text-lg font-semibold">Sign in to AI News Search</h1>
        </div>
        <form action={action} className="space-y-4">
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">Email</label>
            <input
              name="email" type="email" required autoComplete="email"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">Password</label>
            <input
              name="password" type="password" required minLength={8} autoComplete="current-password"
              className="w-full rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none"
            />
          </div>
          {state.error && <p className="text-sm text-destructive">{state.error}</p>}
          <button
            type="submit" disabled={pending}
            className="w-full rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {pending ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          No account? <Link href="/register" className="text-primary hover:underline">Register</Link>
        </p>
      </div>
    </main>
  );
}