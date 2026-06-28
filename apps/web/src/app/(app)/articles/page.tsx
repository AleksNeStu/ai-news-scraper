import Link from "next/link";
import { api } from "@/lib/api";
import { formatRelative } from "@/lib/utils";
import type { ArticleListResponse } from "@ai-news-scraper/shared";

export default async function ArticlesPage({ searchParams }: { searchParams: Promise<{ page?: string }> }) {
  const { page = "1" } = await searchParams;
  const data = await api.get<ArticleListResponse>(`/articles?page=${page}&page_size=20`).catch(() => ({ items: [], total: 0, page: 1, page_size: 20 }));

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="mb-6 text-2xl font-semibold headline-serif">Articles</h1>
      {data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No articles yet.</p>
      ) : (
        <ul className="space-y-3">
          {data.items.map((a) => (
            <li key={a.id}>
              <Link href={`/articles/${a.id}`} className="block rounded-lg border border-border bg-canvas p-4 transition hover:border-primary/40">
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="headline-serif text-base line-clamp-1">{a.headline ?? a.url}</h2>
                  <span className="shrink-0 text-xs text-muted-foreground">{formatRelative(a.indexed_at)}</span>
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{a.source_domain}</span>
                  {a.topics.slice(0, 3).map((t) => (
                    <span key={t} className="rounded bg-muted px-2 py-0.5">{t}</span>
                  ))}
                </div>
                {a.summary && <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{a.summary}</p>}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}