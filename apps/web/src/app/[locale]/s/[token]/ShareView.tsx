'use client'

/**
 * Public share article view (Task #33, ADR-021).
 *
 * Renders the unauthenticated `SharedArticleView` projection that
 * `GET /s/{token}` returns. The view is a STRICT allow-list of fields:
 * we render only `article_id`, `title`, `summary`, `topics`,
 * `source_url`, `published_at`, `shared_at`, and `expires_at`. Anything
 * else the backend might leak (an accidental `owner_id`, `library_id`,
 * `body`, `embedding_vector`, …) is NOT destructured, so the field
 * never reaches the JSX. This is the client-side half of the
 * allow-list contract; the server-side half is in `apps/api/api/
 * schemas/share.py` and ADR-021 §21.3.
 *
 * Loading/error states:
 *   - Loading: nothing rendered (parent <Suspense> fallback is shown).
 *   - 404 (`share_not_found`) or 410 (`share_expired`) → render the
 *     polite "This share link is no longer available" card.
 *   - 5xx / network → render a similar card with a different message.
 *
 * i18n (Task #32): every user-visible string comes from
 * `useTranslations('Share.View')`. Date formatting is locale-aware via
 * `formatTimestamp` from `@/lib/utils`.
 *
 * XSS posture: `title`, `summary`, and `topics` are rendered as plain
 * text (React escapes by default). The shared article view explicitly
 * does NOT render any HTML, so there is no markdown / innerHTML
 * surface to attack.
 */

import { useEffect, useState } from 'react'
import { useLocale, useTranslations } from 'next-intl'
import { AlertTriangle, ExternalLink, Link2 } from 'lucide-react'
import { Link } from '@/i18n/navigation'
import { formatTimestamp } from '@/lib/utils'
import { getSharedArticle, isShareExpired, isShareNotFound } from '@/lib/api/share'
import type { SharedArticleView } from '@ai-news-scraper/shared'

type Phase =
  | { kind: 'loading' }
  | { kind: 'ready'; view: SharedArticleView }
  | { kind: 'gone' }
  | { kind: 'error'; message: string }

export function ShareView({ token }: { token: string }) {
  const t = useTranslations('Share.View')
  const locale = useLocale()
  const [phase, setPhase] = useState<Phase>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    setPhase({ kind: 'loading' })
    getSharedArticle(token)
      .then((view) => {
        if (cancelled) return
        setPhase({ kind: 'ready', view })
      })
      .catch((e: unknown) => {
        if (cancelled) return
        if (isShareExpired(e) || isShareNotFound(e)) {
          setPhase({ kind: 'gone' })
          return
        }
        const msg = e instanceof Error ? e.message : t('error.network')
        setPhase({ kind: 'error', message: msg })
      })
    return () => {
      cancelled = true
    }
  }, [token, t])

  if (phase.kind === 'loading') return null
  if (phase.kind === 'gone') return <GoneCard t={t} />
  if (phase.kind === 'error') return <ErrorCard message={phase.message} t={t} />

  // STRICT allow-list — only these fields are read off the response.
  const { article_id, title, summary, topics, source_url, published_at, shared_at, expires_at } =
    phase.view
  return (
    <main className="min-h-screen">
      <article className="mx-auto max-w-3xl px-6 py-10">
        <header className="space-y-2">
          <h1 className="headline-serif text-3xl">{title}</h1>
          <p className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            {published_at && (
              <span>{t('publishedAt', { date: formatTimestamp(published_at, locale) })}</span>
            )}
            {source_url && (
              <>
                <span aria-hidden="true">·</span>
                <a
                  href={source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  {t('sourceLink')} <ExternalLink className="h-3 w-3" aria-hidden="true" />
                </a>
              </>
            )}
          </p>
        </header>

        {summary && (
          <section className="mt-6 rounded-lg border border-border bg-canvas p-5">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t('summaryHeading')}
            </h2>
            <p className="text-sm leading-relaxed">{summary}</p>
          </section>
        )}

        {topics.length > 0 && (
          <section className="mt-6">
            <h2 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              {t('topicsHeading')}
            </h2>
            <div className="flex flex-wrap gap-2">
              {topics.map((topic) => (
                <span
                  key={topic}
                  className="rounded bg-muted px-2 py-1 text-xs"
                  data-testid="share-topic"
                >
                  {topic}
                </span>
              ))}
            </div>
          </section>
        )}

        <footer className="mt-10 border-t border-border pt-4 text-xs text-muted-foreground">
          <p className="flex items-center gap-2">
            <Link2 className="h-3 w-3" aria-hidden="true" />
            <span>{t('sharedAt', { time: formatTimestamp(shared_at, locale) })}</span>
          </p>
          <p className="mt-1">{t('expiresAt', { time: formatTimestamp(expires_at, locale) })}</p>
          <p className="mt-2 font-mono text-[11px]" data-testid="share-article-id">
            {t('articleIdLabel', { id: article_id })}
          </p>
        </footer>

        <div className="mt-8 text-center">
          <Link href="/" className="text-sm text-muted-foreground hover:text-primary">
            {t('homeLink')}
          </Link>
        </div>
      </article>
    </main>
  )
}

type T = ReturnType<typeof useTranslations<'Share.View'>>

function GoneCard({ t }: { t: T }) {
  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <AlertTriangle className="mb-4 h-10 w-10 text-muted-foreground" aria-hidden="true" />
        <h1 className="headline-serif text-2xl">{t('gone.title')}</h1>
        <p className="mt-3 text-sm text-muted-foreground">{t('gone.body')}</p>
      </div>
    </main>
  )
}

function ErrorCard({ message, t }: { message: string; t: T }) {
  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <AlertTriangle className="mb-4 h-10 w-10 text-destructive" aria-hidden="true" />
        <h1 className="headline-serif text-2xl">{t('error.title')}</h1>
        <p className="mt-3 text-sm text-muted-foreground">{message}</p>
      </div>
    </main>
  )
}
