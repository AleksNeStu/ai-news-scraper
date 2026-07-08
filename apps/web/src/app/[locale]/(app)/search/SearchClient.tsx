'use client'

/**
 * Client-side search UI. Owns the debounced input, in-flight fetch
 * cancellation, and the loading / empty / error / results states.
 *
 * URL is the source of truth — this component reads the query string
 * on every render and writes back via `useFilterUrl`. The server
 * component shell (`page.tsx`) reads the same URL on navigation/refresh
 * and hands the parsed values to this client island via props.
 *
 * Debounce: 250 ms from the last keystroke. Each new keystroke
 * cancels the in-flight request via an `AbortController` so stale
 * results never paint. The `page` cursor is reset to 1 on any text
 * mutation via the URL contract.
 *
 * Empty `q` redirects to `/articles` (per the MVP scope agreed with
 * the user; the page is for semantic search, not browsing).
 */

import * as React from 'react'
import Link from 'next/link'
import { Search as SearchIcon, Loader2 } from 'lucide-react'
import { useRouter } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'

import { searchArticles } from '@/lib/api/search'
import { ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Pagination } from '@/components/Pagination'
import { useFilterUrl } from '@/components/filters/useFilterUrl'
import type { SearchResponse } from '@ai-news-scraper/shared'

const DEBOUNCE_MS = 250

export interface SearchClientProps {
  /** Current `q` from the URL (?q=). Empty string when none. */
  initialQuery: string
  /** Current page (1-indexed). */
  initialPage: number
  /** Current page size. */
  initialPageSize: number
  /** Source filter (exact match on source_domain). */
  initialSource: string | null
  /** Topics filter (multi-value). */
  initialTopics: string[]
  /** From + to date (YYYY-MM-DD). */
  initialFrom: string | null
  initialTo: string | null
}

export function SearchClient(props: SearchClientProps) {
  const t = useTranslations('Search')
  const filters = useFilterUrl()
  const router = useRouter()
  const [q, setQ] = React.useState(props.initialQuery)
  const [pending, setPending] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)
  const [response, setResponse] = React.useState<SearchResponse | null>(null)
  const abortRef = React.useRef<AbortController | null>(null)

  // Debounce the URL write so we don't churn the router on every keystroke.
  // The 250 ms window is the same value ArticlesToolbar uses for its setParams
  // reset (Devil M#1, Task #9 review).
  React.useEffect(() => {
    if (q === props.initialQuery) return
    const handle = setTimeout(() => {
      filters.set('q', q.trim() || null)
      filters.set('page', '1')
    }, DEBOUNCE_MS)
    return () => clearTimeout(handle)
    // We intentionally exclude `filters` and `props.initialQuery` from deps:
    // - `filters` is a stable reference from useFilterUrl's useCallback factory.
    // - `props.initialQuery` would re-fire the effect on URL navigation.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q])

  // Fetch on URL state change. Cancels the previous in-flight request.
  const initialQuery = props.initialQuery
  const initialPage = props.initialPage
  const initialSource = props.initialSource
  const initialTopics = JSON.stringify(props.initialTopics)
  const initialFrom = props.initialFrom
  const initialTo = props.initialTo

  React.useEffect(() => {
    if (!initialQuery) {
      setResponse(null)
      return
    }
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setPending(true)
    setError(null)
    searchArticles({
      query: initialQuery,
      page: initialPage,
      pageSize: props.initialPageSize,
      source: initialSource,
      topics: JSON.parse(initialTopics),
      dateFrom: initialFrom,
      dateTo: initialTo,
    })
      .then((r) => {
        if (ctrl.signal.aborted) return
        setResponse(r)
      })
      .catch((e) => {
        if (ctrl.signal.aborted) return
        if (e instanceof ApiError) setError(e.message)
        else setError(t('failed'))
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setPending(false)
      })
    return () => ctrl.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    initialQuery,
    initialPage,
    initialSource,
    initialTopics,
    initialFrom,
    initialTo,
    props.initialPageSize,
  ])

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!q.trim()) {
      // Empty query: redirect to /articles per the MVP scope.
      router.replace('/articles' as never)
      return
    }
    filters.set('q', q.trim())
    filters.set('page', '1')
  }

  function onRetry() {
    if (!initialQuery) return
    filters.set('q', initialQuery)
  }

  const totalPages =
    response && response.page_size > 0
      ? Math.max(1, Math.ceil(response.total / response.page_size))
      : 1

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <SearchIcon className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">{t('pageTitle')}</h1>
      </div>

      <form
        role="search"
        onSubmit={onSubmit}
        className="rounded-lg border border-border bg-canvas p-6"
      >
        <label htmlFor="search-q" className="mb-2 block text-sm text-muted-foreground">
          {t('queryLabel')}
        </label>
        <div className="flex gap-2">
          <Input
            id="search-q"
            name="q"
            type="search"
            required
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('queryPlaceholder')}
            className="flex-1"
            autoComplete="off"
          />
          <Button type="submit" disabled={pending}>
            {pending ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            ) : (
              <SearchIcon className="h-4 w-4" aria-hidden="true" />
            )}
            {t('submit')}
          </Button>
        </div>
      </form>

      {error && (
        <div
          role="alert"
          aria-live="assertive"
          className="mt-4 rounded-lg border border-destructive/40 bg-canvas p-4"
        >
          <p className="text-sm text-destructive">{error}</p>
          <Button type="button" variant="outline" size="sm" onClick={onRetry} className="mt-2">
            {t('retry')}
          </Button>
        </div>
      )}

      {pending && !response && (
        <div role="status" aria-live="polite" className="mt-8 space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full rounded-lg" />
          ))}
        </div>
      )}

      {response && response.results.length > 0 && (
        <section className="mt-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{t('resultsHeading')}</h2>
            <span className="text-xs text-muted-foreground">
              {t('resultsMeta', {
                count: response.results.length,
                ms: response.took_ms,
              })}
            </span>
          </div>
          <ul className="space-y-3">
            {response.results.map((r) => (
              <li key={r.article.id} className="rounded-lg border border-border bg-canvas p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="headline-serif text-base">
                    {r.article.headline ?? r.article.url}
                  </h3>
                  <span className="shrink-0 rounded bg-muted px-2 py-0.5 text-xs tabular-nums text-primary">
                    {t('score', { n: r.score.toFixed(3) })}
                  </span>
                </div>
                {r.article.summary && (
                  <p className="mt-2 line-clamp-3 text-sm text-muted-foreground">
                    {r.article.summary}
                  </p>
                )}
                <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{r.article.source_domain}</span>
                  {r.article.topics.length > 0 && (
                    <span>· {r.article.topics.slice(0, 3).join(' · ')}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <div className="mt-6">
            <Pagination
              page={response.page}
              totalPages={totalPages}
              onPageChange={(p) => filters.set('page', String(p))}
            />
          </div>
        </section>
      )}

      {response && response.results.length === 0 && !pending && (
        <section
          aria-live="polite"
          className="mt-8 rounded-lg border border-dashed border-border bg-canvas/50 p-8 text-center"
        >
          <h2 className="text-lg font-semibold">{t('noMatchesHeading')}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t('noMatchesBody')}</p>
          <div className="mt-4 flex justify-center gap-2">
            <Link
              href="/articles"
              className="inline-flex items-center justify-center rounded-md border border-input bg-background px-4 py-2 text-sm font-medium hover:bg-accent hover:text-accent-foreground"
            >
              {t('browseArticles')}
            </Link>
          </div>
        </section>
      )}
    </main>
  )
}
