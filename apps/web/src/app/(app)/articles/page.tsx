import Link from "next/link";
import { listArticles } from "@/lib/api/articles";
import { formatRelative } from "@/lib/utils";
import { ScoreRing } from "@/components/ScoreRing";
import { ArticlesToolbar } from "@/app/(app)/articles/ArticlesToolbar";
import { TIER_HEADINGS, TIER_ORDER, bucketByTier, isTier } from "@/app/(app)/articles/buckets";
import type { Article } from "@ai-news-scraper/shared";

export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; tier?: string; group_by_tier?: string }>;
}) {
  const { page = "1", tier, group_by_tier } = await searchParams;
  const grouped = group_by_tier === "true";
  const activeTier = isTier(tier) ? tier : null;
  const empty = { items: [] as Article[], total: 0, page: 1, page_size: 20 };

  const data = grouped
    ? await listArticles({ page: Number(page) || 1, pageSize: 20, groupByTier: true }).catch(() => empty)
    : await listArticles({
        page: Number(page) || 1,
        pageSize: 20,
        tier: activeTier ?? undefined,
      }).catch(() => empty);

  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="mb-6 text-2xl font-semibold headline-serif">Articles</h1>
      <ArticlesToolbar activeTier={activeTier} grouped={grouped} />

      {data.items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No articles yet.</p>
      ) : grouped ? (
        <GroupedView items={data.items} />
      ) : (
        <FlatList items={data.items} />
      )}
    </main>
  );
}

function FlatList({ items }: { items: Article[] }) {
  return (
    <ul className="space-y-3">
      {items.map((a) => (
        <ArticleRow key={a.id} article={a} />
      ))}
    </ul>
  );
}

function GroupedView({ items }: { items: Article[] }) {
  const buckets = bucketByTier(items);
  return (
    <div className="space-y-8">
      {TIER_ORDER.map((t) => {
        const list = buckets[t];
        return (
          <section key={t} aria-labelledby={`tier-${t}`}>
            <header className="mb-3 flex items-baseline justify-between">
              <h2 id={`tier-${t}`} className="text-lg font-semibold headline-serif">
                {TIER_HEADINGS[t]}
              </h2>
              <span className="text-xs text-muted-foreground">{list.length}</span>
            </header>
            {list.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No {TIER_HEADINGS[t].toLowerCase()} articles yet — check back as we score incoming articles.
              </p>
            ) : (
              <ul className="space-y-3">
                {list.map((a) => (
                  <ArticleRow key={a.id} article={a} />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

function ArticleRow({ article }: { article: Article }) {
  return (
    <li>
      <Link
        href={`/articles/${article.id}`}
        className="flex items-start gap-4 rounded-lg border border-border bg-canvas p-4 transition hover:border-primary/40"
      >
        <div className="pt-1">
          <ScoreRing score={article.score} size="sm" tier={article.tier} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="headline-serif text-base line-clamp-1">
              {article.headline ?? article.url}
            </h2>
            <span className="shrink-0 text-xs text-muted-foreground">
              {formatRelative(article.indexed_at)}
            </span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <span>{article.source_domain}</span>
            {article.topics.slice(0, 3).map((t) => (
              <span key={t} className="rounded bg-muted px-2 py-0.5">
                {t}
              </span>
            ))}
          </div>
          {article.summary && (
            <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{article.summary}</p>
          )}
        </div>
      </Link>
    </li>
  );
}
