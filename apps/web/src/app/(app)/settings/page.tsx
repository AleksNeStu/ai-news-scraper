import { Settings as SettingsIcon } from "lucide-react";

export default function SettingsPage() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <SettingsIcon className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">Settings</h1>
      </div>

      <section className="space-y-4">
        <div className="rounded-lg border border-border bg-canvas p-5">
          <h2 className="font-medium">Account</h2>
          <p className="mt-1 text-sm text-muted-foreground">Signed in. Account settings live in a future iteration (P1).</p>
        </div>
        <div className="rounded-lg border border-border bg-canvas p-5">
          <h2 className="font-medium">OpenAI key</h2>
          <p className="mt-1 text-sm text-muted-foreground">Server-side only for MVP. Bring-your-own-key is P1.</p>
        </div>
        <div className="rounded-lg border border-border bg-canvas p-5">
          <h2 className="font-medium">Default summarizer</h2>
          <p className="mt-1 text-sm text-muted-foreground">gpt-4o-mini (OpenAI). Switchable to Anthropic in P1.</p>
        </div>
      </section>
    </main>
  );
}
