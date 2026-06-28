"use client";

import { useState } from "react";
import { Rss, Plus, Trash2, Loader2, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { FeedListResponse, FeedItemOut, FeedOut } from "@ai-news-scraper/shared";
import { useRouter } from "next/navigation";

export default function FeedsPage() {
  const router = useRouter();
  const [feedUrl, setFeedUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<FeedListResponse>({ items: [], total: 0 });
  const [pollResult, setPollResult] = useState<FeedItemOut[] | null>(null);

  async function load() {
    const r = await api.get<FeedListResponse>("/feeds").catch(() => ({ items: [], total: 0 }));
    setData(r);
  }
  // initial load (client-side; cheap)
  if (data.items.length === 0 && !pending) load();

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!feedUrl) return;
    setPending(true); setError(null);
    try {
      await api.post<FeedOut>("/feeds", { feed_url: feedUrl });
      setFeedUrl("");
      await load();
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Add failed");
    } finally { setPending(false); }
  }

  async function onDelete(id: string) {
    if (!confirm("Unsubscribe?")) return;
    await api.delete(`/feeds/${id}`);
    await load();
    router.refresh();
  }

  async function onPoll(id: string) {
    setPending(true); setError(null); setPollResult(null);
    try {
      const items = await api.post<FeedItemOut[]>(`/feeds/${id}/poll`);
      setPollResult(items);
      await load();
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
    } finally { setPending(false); }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <Rss className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">RSS feeds</h1>
      </div>

      <form onSubmit={onAdd} className="rounded-lg border border-border bg-canvas p-5">
        <label className="mb-2 block text-sm text-muted-foreground">Feed URL</label>
        <div className="flex gap-2">
          <input type="url" required value={feedUrl} onChange={(e) => setFeedUrl(e.target.value)}
            placeholder="https://example.com/feed.xml"
            className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none" />
          <button type="submit" disabled={pending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50">
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Subscribe
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      </form>

      {pollResult && (
        <p className="mt-4 text-sm text-muted-foreground">Polled — {pollResult.length} new items.</p>
      )}

      <section className="mt-8 space-y-3">
        {data.items.length === 0 ? (
          <p className="text-sm text-muted-foreground">No subscriptions yet.</p>
        ) : data.items.map((f) => (
          <div key={f.id} className="flex items-center justify-between rounded-lg border border-border bg-canvas p-4">
            <div className="min-w-0">
              <h3 className="truncate font-medium">{f.title ?? f.feed_url}</h3>
              <p className="truncate text-xs text-muted-foreground">{f.feed_url}</p>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>{f.item_count} items</span>
              <button onClick={() => onPoll(f.id)} className="rounded-md border border-border bg-surface p-1.5 hover:border-primary/40" aria-label="Poll now">
                <RefreshCw className="h-4 w-4" />
              </button>
              <button onClick={() => onDelete(f.id)} className="rounded-md border border-border bg-surface p-1.5 hover:border-destructive/40" aria-label="Unsubscribe">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          </div>
        ))}
      </section>
    </main>
  );
}