'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeft, ExternalLink, Newspaper } from 'lucide-react'
import { useDigest } from '@/hooks/useDigest'
import type { DigestSection } from '@ai-news-scraper/shared'

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

export default function DigestDetailPage() {
  const params = useParams<{ date: string }>()
  const raw = params?.date ?? ''
  const date = DATE_RE.test(raw) ? raw : ''

  const { data, loading, error, disabled } = useDigest(date || null)

  if (!date) {
    return <NotFoundState message="Invalid date format." />
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10 space-y-4" aria-label="Loading brief">
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
          {error}
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
          <ArrowLeft className="h-4 w-4" /> Back to briefs
        </Link>
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-10 text-center">
          <Newspaper className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
          <h2 className="font-medium">Daily briefs are temporarily unavailable</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            We&apos;re working on it — check back soon.
          </p>
        </div>
      </div>
    )
  }

  if (!data) {
    return <NotFoundState date={date} />
  }

  return (
    <article className="mx-auto max-w-3xl px-6 py-10">
      <Link
        href="/dashboard/brief"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> Back to briefs
      </Link>

      <header className="mb-8">
        <h1 className="headline-serif text-3xl">{formatLongDate(data.for_date)}</h1>
        <div className="mt-2 text-xs uppercase tracking-wider text-muted-foreground">
          Daily brief · {data.sections.length} {data.sections.length === 1 ? 'section' : 'sections'}
        </div>
      </header>

      <section className="rounded-lg border border-border bg-canvas p-6">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Overall summary
        </h2>
        {data.overall_summary ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{data.overall_summary}</p>
        ) : (
          <p className="text-sm italic text-muted-foreground">
            No new articles today — your library is quiet.
          </p>
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
  return (
    <section
      id={`section-${section.cluster_id}`}
      className="rounded-lg border border-border bg-canvas p-6 scroll-mt-20"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h3 className="headline-serif text-xl">{section.topic}</h3>
        {section.article_ids.length > 0 && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {section.article_ids.length} {section.article_ids.length === 1 ? 'source' : 'sources'}
          </span>
        )}
      </div>
      <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed">{section.summary}</p>
      {section.article_ids.length > 0 && (
        <div className="mt-4 border-t border-border pt-3">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Sources
          </h4>
          <ul className="space-y-1">
            {section.article_ids.map((id) => (
              <li key={id}>
                <Link
                  href={`/articles/${id}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  Article {id.slice(0, 8)} <ExternalLink className="h-3 w-3" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}

function NotFoundState({ date, message }: { date?: string; message?: string }) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <Link
        href="/dashboard/brief"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-primary"
      >
        <ArrowLeft className="h-4 w-4" /> Back to briefs
      </Link>
      <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-10 text-center">
        <Newspaper className="mx-auto mb-3 h-8 w-8 text-muted-foreground" />
        <h2 className="font-medium">
          {message ?? (date ? `No brief for ${formatLongDate(date)}` : 'No brief')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Digests are generated each morning at 08:00 (your local time).
        </p>
      </div>
    </div>
  )
}

function formatLongDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`)
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
