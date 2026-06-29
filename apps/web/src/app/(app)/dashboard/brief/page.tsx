'use client'

import Link from 'next/link'
import { Newspaper, Loader2 } from 'lucide-react'
import { useDigestList } from '@/hooks/useDigest'
import { cn } from '@/lib/utils'

const PREVIEW_CHARS = 200

export default function BriefInboxPage() {
  const { data, loading, error, disabled } = useDigestList(20)

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <Newspaper className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">Daily Briefs</h1>
      </div>

      {loading && (
        <ul className="space-y-3" aria-label="Loading briefs">
          {Array.from({ length: 3 }).map((_, i) => (
            <li key={i} className="skeleton h-28 rounded-lg" />
          ))}
        </ul>
      )}

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-canvas p-4 text-sm text-destructive">
          {error}
        </p>
      )}

      {!loading && !error && disabled && (
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
          <h4 className="font-medium">Daily briefs are temporarily unavailable</h4>
          <p className="mt-1 text-sm text-muted-foreground">
            We&apos;re working on it — check back soon.
          </p>
        </div>
      )}

      {!loading && !error && !disabled && data && data.digests.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center">
          <h4 className="font-medium">No briefs yet</h4>
          <p className="mt-1 text-sm text-muted-foreground">
            Your first daily brief will appear here — check back tomorrow.
          </p>
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
                    <h2 className="headline-serif text-lg">{formatDate(d.for_date)}</h2>
                    <span className="shrink-0 rounded bg-muted px-2 py-0.5 text-xs tabular-nums text-muted-foreground">
                      {d.sections.length} {d.sections.length === 1 ? 'section' : 'sections'}
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
                      No new articles today.
                    </p>
                  )}
                  <div className="mt-3 flex justify-end">
                    <span className="text-sm text-primary">View →</span>
                  </div>
                </Link>
              </li>
            )
          })}
          {loading && (
            <li className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Refreshing…
            </li>
          )}
        </ul>
      )}
    </div>
  )
}

function formatDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`)
  return d.toLocaleDateString(undefined, {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}
