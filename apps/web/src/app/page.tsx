import Link from "next/link";
import { Newspaper, Search, Rss, Settings, LogOut } from "lucide-react";
import { logoutAction } from "@/lib/auth";
import { api } from "@/lib/api";
import type { ArticleListResponse, FeedListResponse } from "@ai-news-scraper/shared";

export default async function DashboardPage() {
  const [articles, feeds] = await Promise.all([
    api.get<ArticleListResponse>("/articles?page=1&page_size=5").catch(() => ({ items: [], total: 0, page: 1, page_size: 5 })),
    api.get<FeedListResponse>("/feeds").catch(() => ({ items: [], total: 0 })),
  ]);

  return (
    <main className="min-h-screen">
      <header className="border-b border-border bg-canvas">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <Newspaper className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-semibold tracking-tight">AI News Search</h1>
          </div>
          <nav className="flex items-center gap-1">
            <NavLink href="/scrape" icon={<Newspaper className="h-4 w-4" />}>Scrape</NavLink>
            <NavLink href="/search" icon={<Search className="h-4 w-4" />}>Search</NavLink>
            <NavLink href="/articles" icon={<Newspaper className="h-4 w-4" />}>Articles</NavLink>
            <NavLink href="/feeds" icon={<Rss className="h-4 w-4" />}>Feeds</NavLink>
            <NavLink href="/settings" icon={<Settings className="h-4 w-4" />}>Settings</NavLink>
            <form action={logoutAction}>
              <button className="ml-2 inline-flex items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-primary/40">
                <LogOut className="h-4 w-4" /> Logout
              </button>
            </form>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-10 space-y-8">
        <section>
          <h2 className="text-2xl font-semibold headline-serif">Welcome back</h2>
          <p className="mt-1 text-muted-foreground">Your personal semantic news library.</p>
        </section>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <StatCard label="Total articles" value={articles.total} href="/articles" />
          <StatCard label="Active feeds" value={feeds.items.filter((f) => f.active).length} href="/feeds" />
          <StatCard label="Indexed today" value={0} href="/articles" />
        </div>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold">Recent articles</h3>
            <Link href="/articles" className="text-sm text-primary hover:underline">View all →</Link>
          </div>
          <div className="space-y-3">
            {articles.items.length === 0 ? (
              <EmptyState
                title="No articles yet"
                body="Scrape your first URL or subscribe to an RSS feed to get started."
                cta={{ href: "/scrape", label: "Scrape a URL" }}
              />
            ) : (
              articles.items.map((a) => (
                <Link
                  key={a.id}
                  href={`/articles/${a.id}`}
                  className="block rounded-lg border border-border bg-canvas p-4 transition hover:border-primary/40"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <h4 className="headline-serif text-base line-clamp-1">{a.headline ?? a.url}</h4>
                    <span className="shrink-0 text-xs text-muted-foreground">{a.source_domain}</span>
                  </div>
                  {a.summary && <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.summary}</p>}
                </Link>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  );
}

function NavLink({ href, icon, children }: { href: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <Link href={href} className="inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-surface hover:text-foreground">
      {icon} {children}
    </Link>
  );
}

function StatCard({ label, value, href }: { label: string; value: number; href: string }) {
  return (
    <Link href={href} className="rounded-lg border border-border bg-canvas p-5 transition hover:border-primary/40">
      <div className="text-3xl font-semibold tabular-nums text-primary">{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{label}</div>
    </Link>
  );
}

function EmptyState({ title, body, cta }: { title: string; body: string; cta: { href: string; label: string } }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
      <h4 className="font-medium">{title}</h4>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      <Link href={cta.href} className="mt-4 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
        {cta.label}
      </Link>
    </div>
  );
}
