'use client'

import { useState } from 'react'
import { Search as SearchIcon, Loader2 } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { api, ApiError } from '@/lib/api'
import type { SearchResponse } from '@ai-news-scraper/shared'

/**
 * /search page (Task #32). Client component. Strings come from
 * `useTranslations('Search')`. The score line uses an ICU placeholder
 * for the formatted number so Russian text reads "скор 0,876" with the
 * locale-specific decimal separator.
 */
export default function SearchPage() {
  const t = useTranslations('Search')
  const [q, setQ] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<SearchResponse | null>(null)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!q.trim()) return
    setPending(true)
    setError(null)
    try {
      const r = await api.post<SearchResponse>('/search', { query: q, top_k: 10 })
      setResponse(r)
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError(t('failed'))
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <SearchIcon className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">{t('pageTitle')}</h1>
      </div>

      <form onSubmit={onSubmit} className="rounded-lg border border-border bg-canvas p-6">
        <label className="mb-2 block text-sm text-muted-foreground">{t('queryLabel')}</label>
        <div className="flex gap-2">
          <input
            type="search"
            required
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={t('queryPlaceholder')}
            className="flex-1 rounded-md border border-border bg-surface px-3 py-2 text-sm focus:border-primary focus:outline-none"
          />
          <button
            type="submit"
            disabled={pending}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            {pending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <SearchIcon className="h-4 w-4" />
            )}
            {t('submit')}
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
      </form>

      {response && (
        <section className="mt-8">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">{t('resultsHeading')}</h2>
            <span className="text-xs text-muted-foreground">
              {t('resultsMeta', { count: response.results.length, ms: response.took_ms })}
            </span>
          </div>
          {response.results.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t('noMatches')}</p>
          ) : (
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
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </main>
  )
}
