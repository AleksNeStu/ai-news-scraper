import Link from 'next/link'
import type { Route } from 'next'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import { api } from '@/lib/api'
import { AppHeader } from '@/components/layout/AppHeader'
import type { ArticleListResponse, FeedListResponse } from '@ai-news-scraper/shared'

/**
 * Home page (Task #32). Sits under the new `[locale]` segment so the
 * `AppHeader` and link hrefs resolve via next-intl's locale-aware
 * navigation. Default locale renders at bare `/`; non-default locales
 * render at `/ru`.
 *
 * All user-visible strings flow through `getTranslations('Home')`.
 *
 * `setRequestLocale(locale)` MUST come before any `getTranslations` /
 * `useTranslations` call so next-intl resolves the catalog on a
 * static-rendered page; the `[locale]/layout.tsx` also calls it, but
 * the docs recommend also calling it in every page for static export.
 */
export default async function HomePage({
  params,
}: {
  params: { locale: string }
}) {
  const { locale } = params
  setRequestLocale(locale)
  const t = await getTranslations('Home')
  const [articles, feeds] = await Promise.all([
    api
      .get<ArticleListResponse>('/articles?page=1&page_size=5')
      .catch(() => ({ items: [], total: 0, page: 1, page_size: 5 })),
    api.get<FeedListResponse>('/feeds').catch(() => ({ items: [], total: 0 })),
  ])

  return (
    <main className="min-h-screen">
      <AppHeader />

      <div className="mx-auto max-w-6xl px-6 py-10 space-y-8">
        <section>
          <h2 className="text-2xl font-semibold headline-serif">{t('welcomeHeading')}</h2>
          <p className="mt-1 text-muted-foreground">{t('welcomeBody')}</p>
        </section>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
          <StatCard
            label={t('stat.totalArticles')}
            value={articles.total}
            href="/articles"
          />
          <StatCard
            label={t('stat.activeFeeds')}
            value={feeds.items.filter((f) => f.active).length}
            href="/feeds"
          />
          <StatCard label={t('stat.indexedToday')} value={0} href="/articles" />
        </div>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-lg font-semibold">{t('recentArticles')}</h3>
            <Link href="/articles" className="text-sm text-primary hover:underline">
              {t('viewAll')}
            </Link>
          </div>
          <div className="space-y-3">
            {articles.items.length === 0 ? (
              <EmptyState
                title={t('empty.title')}
                body={t('empty.body')}
                cta={{ href: '/scrape', label: t('empty.cta') }}
              />
            ) : (
              articles.items.map((a) => (
                <Link
                  key={a.id}
                  href={`/articles/${a.id}` as Route}
                  className="block rounded-lg border border-border bg-canvas p-4 transition hover:border-primary/40"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <h4 className="headline-serif text-base line-clamp-1">{a.headline ?? a.url}</h4>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {a.source_domain}
                    </span>
                  </div>
                  {a.summary && (
                    <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.summary}</p>
                  )}
                </Link>
              ))
            )}
          </div>
        </section>
      </div>
    </main>
  )
}

function StatCard({ label, value, href }: { label: string; value: number; href: string }) {
  return (
    <Link
      href={href as Route}
      className="rounded-lg border border-border bg-canvas p-5 transition hover:border-primary/40"
    >
      <div className="text-3xl font-semibold tabular-nums text-primary">{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{label}</div>
    </Link>
  )
}

function EmptyState({
  title,
  body,
  cta,
}: {
  title: string
  body: string
  cta: { href: string; label: string }
}) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
      <h4 className="font-medium">{title}</h4>
      <p className="mt-1 text-sm text-muted-foreground">{body}</p>
      <Link
        href={cta.href as Route}
        className="mt-4 inline-block rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
      >
        {cta.label}
      </Link>
    </div>
  )
}
