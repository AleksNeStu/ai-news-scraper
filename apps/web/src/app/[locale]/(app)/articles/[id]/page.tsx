import { notFound } from 'next/navigation'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import { ArrowLeft } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { api } from '@/lib/api'
import { formatDate, formatRelative } from '@/lib/utils'
import type { ArticleOut } from '@ai-news-scraper/shared'

/**
 * /articles/[id] page (Task #32). Locale-aware server component.
 *
 * Notes:
 *   - `formatDate(a.publish_date, locale)` and
 *     `formatRelative(a.indexed_at, locale)` resolve in the active locale.
 *   - `Indexed {relative}` / `Published {date}` use ICU placeholders in
 *     the ArticleDetail namespace, defined in `messages/{en,ru}.json`.
 */
export default async function ArticleDetailPage({
  params,
}: {
  params: Promise<{ id: string; locale: string }>
}) {
  const { id, locale } = await params
  setRequestLocale(locale)
  const a = await api.get<ArticleOut>(`/articles/${id}`).catch(() => null)
  if (!a) notFound()

  const t = await getTranslations('ArticleDetail')

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <Link
        href="/articles"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> {t('backToArticles')}
      </Link>
      <article className="space-y-6">
        <header>
          <h1 className="headline-serif text-3xl">{a.headline ?? a.url}</h1>
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span>{a.source_domain}</span>
            <span>·</span>
            <span>{t('indexedAt', { relative: formatRelative(a.indexed_at) })}</span>
            {a.publish_date && (
              <>
                <span>·</span>
                <span>{t('publishedAt', { date: formatDate(a.publish_date) })}</span>
              </>
            )}
            <a
              href={a.url}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto text-primary hover:underline"
            >
              {t('originalLink')}
            </a>
          </div>
        </header>
        {a.summary && (
          <section className="rounded-lg border border-border bg-canvas p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t('summary')}
            </h2>
            <p className="text-sm leading-relaxed">{a.summary}</p>
          </section>
        )}
        {a.topics.length > 0 && (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t('topics')}
            </h2>
            <div className="flex flex-wrap gap-2">
              {a.topics.map((topic) => (
                <span key={topic} className="rounded bg-muted px-2 py-1 text-xs">
                  {topic}
                </span>
              ))}
            </div>
          </section>
        )}
        {a.body && (
          <section>
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t('fullText')}
            </h2>
            <div className="whitespace-pre-wrap text-sm leading-relaxed">{a.body}</div>
          </section>
        )}
      </article>
    </main>
  )
}
