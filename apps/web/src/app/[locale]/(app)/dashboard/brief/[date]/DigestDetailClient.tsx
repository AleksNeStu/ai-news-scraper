'use client'

import { useParams } from 'next/navigation'
import { ArrowLeft, ExternalLink, Newspaper } from 'lucide-react'
import { useLocale, useTranslations } from 'next-intl'
import { Link } from '@/i18n/navigation'
import { useDigest } from '@/hooks/useDigest'
import { formatLongDate } from '@/lib/utils'
import type { DigestSection } from '@ai-news-scraper/shared'

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Daily Brief detail page (Task #32). Client component driven by
 * `useDigest(date)`. All strings come from
 * `useTranslations('Brief.Detail')` and the active locale is read
 * via `useLocale()` so the long-date formatter renders in the right
 * language.
 *
 * i18n notes:
 *   - `sectionCount` uses ICU plural — RU requires one/few/many for
 *     "раздел / раздела / разделов".
 *   - `notFound.titleWithDate` injects the formatted date into the
 *     "No brief for {date}" heading.
 *   - `articleLinkAria` uses the article id prefix (matches the
 *     original English copy "Article {id.slice(0,8)}").
 *
 * Task #28 split: this file is the client-only render shell. The
 * server-component `page.tsx` (same folder) owns the JSON-LD +
 * `generateMetadata`, then renders `<DigestDetailClient />` passing
 * the validated date through props.
 */
export default function DigestDetailClient() {
  const t = useTranslations('Brief.Detail')
  const tErrors = useTranslations('Errors')
  const locale = useLocale()
  const params = useParams<{ date: string }>()
  const raw = params?.date ?? ''
  const date = DATE_RE.test(raw) ? raw : ''

  const { data, loading, error, disabled } = useDigest(date || null)

  if (!date) {
    return <NotFoundState message={t('notFound.title')} />
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10 space-y-4" aria-label={t('loadingAria')}>
        <div className="skeleton h-8 w-1/2 rounded" />
        <div className="skeleton h-6 w-full rounded" />
        <div className="skeleton h-32 w-full rounded-lg" />
        <div className="skeleton h-32 w-full rounded-lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <p className="rounded-lg border border-destructive/40 bg-canvas p-4 text-sm text-destructive">
          {error || tErrors('failedToLoad')}
        </p>
      </div>
    )
  }

  if (disabled) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <Link
          href="/dashboard/brief"
          className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
        >
          <ArrowLeft className="h-4 w-4" /> {t('backToBriefs')}
        </Link>
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-10 text-center">
          <Newspaper className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
          <h2 className="font-medium">{t('disabled.title')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('disabled.body')}</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return <NotFoundState date={date} locale={locale} />
  }

  return (
    <article className="mx-auto max-w-3xl px-6 py-10">
      <Link
        href="/dashboard/brief"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> {t('backToBriefs')}
      </Link>

      <header className="mb-8">
        <h1 className="headline-serif text-3xl">{formatLongDate(data.for_date, locale)}</h1>
        <div className="mt-2 text-xs uppercase tracking-wider text-muted-foreground">
          {t('sectionCount', { count: data.sections.length })}
        </div>
      </header>

      <section className="rounded-lg border border-border bg-canvas p-6">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          {t('overallSummary')}
        </h2>
        {data.overall_summary ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{data.overall_summary}</p>
        ) : (
          <p className="text-sm italic text-muted-foreground">{t('noArticlesToday')}</p>
        )}
      </section>

      {data.sections.length > 0 && (
        <section className="mt-10 space-y-8">
          {data.sections
            .slice()
            .sort((a, b) => a.rank - b.rank)
            .map((s) => (
              <DigestSectionCard key={s.cluster_id} section={s} />
            ))}
        </section>
      )}
    </article>
  )
}

function DigestSectionCard({ section }: { section: DigestSection }) {
  const t = useTranslations('Brief.Detail')
  return (
    <section
      id={`section-${section.cluster_id}`}
      className="rounded-lg border border-border bg-canvas p-6 scroll-mt-20"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="headline-serif text-xl">{section.topic}</h3>
        {section.article_ids.length > 0 && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {t('sourceCount', { count: section.article_ids.length })}
          </span>
        )}
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{section.summary}</p>
      {section.article_ids.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {t('sourcesHeading')}
          </h4>
          <ul className="space-y-1">
            {section.article_ids.map((id) => (
              <li key={id}>
                <Link
                  href={`/articles/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                  aria-label={t('articleLinkAria', { id: id.slice(0, 8) })}
                >
                  {id.slice(0, 8)} <ExternalLink className="h-3 w-3" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function NotFoundState({
  date,
  message,
  locale,
}: {
  date?: string
  message?: string
  locale?: string
}) {
  const t = useTranslations('Brief.Detail')
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link
        href="/dashboard/brief"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> {t('backToBriefs')}
      </Link>
      <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-10 text-center">
        <Newspaper className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <h2 className="font-medium">
          {message ??
            (date
              ? t('notFound.titleWithDate', { date: formatLongDate(date, locale) })
              : t('notFound.title'))}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('notFound.body')}</p>
      </div>
    </div>
  )
}
