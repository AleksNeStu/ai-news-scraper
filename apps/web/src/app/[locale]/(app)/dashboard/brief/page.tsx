'use client'

import { Newspaper, Loader2 } from 'lucide-react'
import { useLocale, useTranslations } from 'next-intl'
import { Link } from '@/i18n/navigation'
import { useDigestList } from '@/hooks/useDigest'
import { formatLongDate } from '@/lib/utils'
import { cn } from '@/lib/utils'

const PREVIEW_CHARS = 200

/**
 * Daily Brief inbox (Task #32). Client component driven by
 * `useDigestList`. Strings come from `useTranslations('Brief.Inbox')`.
 *
 * i18n notes:
 *   - `sectionCount` is an ICU plural so "1 section" / "5 sections"
 *     reads grammatically correct in both locales (Russian needs
 *     one/few/many).
 *   - `formatLongDate(for_date, locale)` delegates to Intl-backed
 *     `lib/utils.ts`.
 *   - Errors flow through the `Errors` namespace so the messages here
 *     are localized consistently across hooks (useDigest, useNotifications,
 *     useUnreadCount).
 */
export default function BriefInboxPage() {
  const t = useTranslations('Brief.Inbox')
  const tErrors = useTranslations('Errors')
  const locale = useLocale()
  const { data, loading, error, disabled } = useDigestList(20)

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <Newspaper className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">{t('title')}</h1>
      </div>

      {loading && (
        <ul className="space-y-3" aria-label={t('loadingAria')}>
          {Array.from({ length: 3 }).map((_, i) => (
            <li key={i} className="skeleton h-28 rounded-lg" />
          ))}
        </ul>
      )}

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-canvas p-4 text-sm text-destructive">
          {error || tErrors('failedToLoad')}
        </p>
      )}

      {!loading && !error && disabled && (
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
          <h4 className="font-medium">{t('disabled.title')}</h4>
          <p className="mt-1 text-sm text-muted-foreground">{t('disabled.body')}</p>
        </div>
      )}

      {!loading && !error && !disabled && data && data.digests.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
          <h4 className="font-medium">{t('empty.title')}</h4>
          <p className="mt-1 text-sm text-muted-foreground">{t('empty.body')}</p>
        </div>
      )}

      {!loading && !error && !disabled && data && data.digests.length > 0 && (
        <ul className="space-y-3">
          {data.digests.map((d) => {
            const preview = d.overall_summary.slice(0, PREVIEW_CHARS)
            const truncated = d.overall_summary.length > PREVIEW_CHARS
            return (
              <li key={d.id}>
                <Link
                  href={`/dashboard/brief/${d.for_date}`}
                  className="block rounded-lg border border-border bg-canvas p-5 transition hover:border-primary/40"
                >
                  <div className="flex items-baseline justify-between gap-3">
                    <h2 className="headline-serif text-lg">{formatLongDate(d.for_date, locale)}</h2>
                    <span className="shrink-0 rounded bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
                      {t('sectionCount', { count: d.sections.length })}
                    </span>
                  </div>
                  {d.overall_summary && (
                    <p
                      className={cn(
                        'mt-2 text-sm text-muted-foreground',
                        !truncated && 'line-clamp-3'
                      )}
                    >
                      {preview}
                      {truncated && '…'}
                    </p>
                  )}
                  {!d.overall_summary && (
                    <p className="mt-2 text-sm italic text-muted-foreground">
                      {t('noArticlesToday')}
                    </p>
                  )}
                  <div className="mt-3 flex justify-end">
                    <span className="text-sm text-primary">{t('view')}</span>
                  </div>
                </Link>
              </li>
            )
          })}
          {loading && (
            <li className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> {t('refreshing')}
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
