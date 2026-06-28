"use client";

import { useState } from "react";
import { Newspaper, Plus, Loader2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { ArticleOut } from "@ai-news-scraper/shared";

export default function ScrapePage() {
  const [url, setUrl] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ArticleOut[]>([]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!url) return;
    setPending(true);
    setError(null);
    try {
      const article = await api.post<ArticleOut>("/scrape", { url });
      setResults((r) => [article, ...r]);
      setUrl("");
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else setError("Scrape failed");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <Newspaper className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">Scrape a URL</h1>
      </div>

      <form onSubmit={onSubmit} className="rounded-lg border border-border bg-canvas p-6">
        <label className="mb-2 block text-sm text-muted-foreground">Article URL</label>
        <div className="flex gap-2">
          <input
            type="url" required value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/article"
            className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
          <button
            type="submit" disabled={pending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Scrape
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      </form>

      <section className="mt-8">
        <h2 className="mb-3 text-lg font-semibold">Recent scrapes</h2>
        {results.length === 0 ? (
          <p className="text-sm text-muted-foreground">No scrapes yet in this session.</p>
        ) : (
          <ul className="space-y-3">
            {results.map((a) => (
              <li key={a.id} className="rounded-lg border border-border bg-canvas p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="headline-serif text-base">{a.headline ?? a.url}</h3>
                  <span className="shrink-0 text-xs text-muted-foreground">{a.source_domain}</span>
                </div>
                {a.summary && <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">{a.summary}</p>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}