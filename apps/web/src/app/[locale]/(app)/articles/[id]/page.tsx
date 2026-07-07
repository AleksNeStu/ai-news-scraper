import { notFound } from 'next/navigation'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import type { Metadata } from 'next'
import { ArrowLeft } from 'lucide-react'
import { Link, getPathname } from '@/i18n/navigation'
import { api } from '@/lib/api'
import { formatDate, formatRelative } from '@/lib/utils'
import { StructuredData } from '@/components/StructuredData'
import { SITE_URL } from '@/lib/site'
import { buildArticleJsonLd, buildBreadcrumbJsonLd } from '@/lib/structured-data/builders'
import type { ArticleOut } from '@ai-news-scraper/shared'

/**
 * /articles/[id] page (Task #32). Locale-aware server component.
 *
 * Notes:
 *   - `formatDate(a.publish_date, locale)` and
 *     `formatRelative(a.indexed_at, locale)` resolve in the active locale.
 *   - `Indexed {relative}` / `Published {date}` use ICU placeholders in
 *     the ArticleDetail namespace, defined in `messages/{en,ru}.json`.
 *
 * GEO readiness (Task #28):
 *   - `generateMetadata` returns canonical + og:* (article variant) +
 *     twitter:*.
 *   - The rendered tree carries Article + BreadcrumbList JSON-LD so the
 *     headline + publication date + canonical URL are machine-readable.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string; locale: string }>
}): Promise<Metadata> {
  const { id, locale } = await params
  const a = await api.get<ArticleOut>(`/articles/${id}`).catch(() => null)
  const headline = a?.headline ?? a?.url ?? 'Article'
  const description = a?.summary ?? undefined
  const path = `/articles/${id}`
  const canonical = `${SITE_URL}${getPathname({ locale: locale as 'en' | 'ru', href: path })}`
  return {
    title: headline,
    ...(description ? { description } : {}),
    alternates: { canonical },
    openGraph: {
      title: headline,
      ...(description ? { description } : {}),
      type: 'article',
      url: canonical,
      siteName: 'ai-news-scraper',
      locale: locale === 'en' ? 'en_US' : 'ru_RU',
      ...(a?.publish_date ? { publishedTime: a.publish_date } : {}),
      ...(a?.source_domain ? { authors: [a.source_domain] } : {}),
    },
    twitter: {
      card: 'summary_large_image',
      title: headline,
      ...(description ? { description } : {}),
    },
  }
}

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

  const articlePath = getPathname({ locale: locale as 'en' | 'ru', href: `/articles/${id}` })
  const articlesIndexPath = getPathname({ locale: locale as 'en' | 'ru', href: '/articles' })
  const homePath = getPathname({ locale: locale as 'en' | 'ru', href: '/' })
  const headline = a.headline ?? a.url

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      {/* GEO readiness (Task #28): Article JSON-LD surfaces headline +
          publication date + canonical URL; BreadcrumbList gives the
          Home → Articles → <headline> trail. */}
      <StructuredData
        data={[
          buildArticleJsonLd({
            id: a.id,
            headline,
            datePublished: a.publish_date ?? a.indexed_at,
            ...(a.summary ? { description: a.summary } : {}),
            ...(a.topics.length > 0 ? { keywords: a.topics.join(', ') } : {}),
            locale: locale as 'en' | 'ru',
            canonicalPath: articlePath,
          }),
          buildBreadcrumbJsonLd([
            { name: 'Home', path: homePath },
            { name: t('backToArticles'), path: articlesIndexPath },
            { name: headline, path: articlePath },
          ]),
        ]}
      />
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
            <span>{t('indexedAt', { relative: formatRelative(a.indexed_at, locale) })}</span>
            {a.publish_date && (
              <>
                <span>·</span>
                <span>{t('publishedAt', { date: formatDate(a.publish_date, locale) })}</span>
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
