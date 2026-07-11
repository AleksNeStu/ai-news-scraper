'use client'

import { useState } from 'react'
import { Rss, Loader2, AlertTriangle, CheckCircle2, RotateCcw, XCircle } from 'lucide-react'
import { useTranslations } from 'next-intl'
import { Link } from '@/i18n/navigation'
import { api, ApiError } from '@/lib/api'
import type { OpmlFeedRef, BulkImportRequest, BulkImportResult } from '@ai-news-scraper/shared'

/**
 * /feeds/import page (Task #35, ADR-024).
 *
 * Client component. Two phases:
 *   1. `parsed` — user uploaded an OPML file; we ran DOMParser on it,
 *      extracted every `<outline xmlUrl=...>` leaf into a local
 *      `OpmlFeedRef[]`, and the user is choosing which subset to submit
 *      (default: all selected). The `category` field is parsed from the
 *      OPML outline path and discarded before POST (the v1 backend does
 *      not persist it).
 *   2. `submitting` / `success` / `error` — POST `/feeds/bulk`, render
 *      partial-success badges + per-item failure list on success, or
 *      surface `e.message` on error (the API returns localised error
 *      detail for 4xx so the user sees "Too many feeds (max 500)" etc.
 *      directly).
 *
 * OPML parsing happens in the browser via DOMParser — no external
 * library. The recursive outline walk handles the standard nesting
 * pattern (Feedly / Inoreader group feeds under category folders like
 * `<outline text="Tech"><outline xmlUrl=.../></outline>`).
 */
type Phase = 'idle' | 'parsed' | 'submitting' | 'success' | 'error'

const MAX_FEEDS = 500

export default function ImportPage() {
  const t = useTranslations('Feeds')
  const [phase, setPhase] = useState<Phase>('idle')
  const [feeds, setFeeds] = useState<OpmlFeedRef[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<BulkImportResult | null>(null)
  const [parsedTitles, setParsedTitles] = useState<Map<string, string>>(new Map())

  /**
   * Recursively walk `<outline>` elements, collecting every leaf that
   * carries an `xmlUrl` (or `xmlurl` — Feedly mixes case). The parent
   * `text`/`title` attribute becomes the `category` prefix, joined with
   * " > " for nested folders.
   */
  function walkOutlines(
    outlines: HTMLCollectionOf<Element> | Element[],
    parentCategory: string
  ): OpmlFeedRef[] {
    const out: OpmlFeedRef[] = []
    for (let i = 0; i < outlines.length; i++) {
      const el = outlines[i]
      const xmlUrl =
        el.getAttribute('xmlUrl') ?? el.getAttribute('xmlurl') ?? el.getAttribute('XMLURL')
      const titleAttr = el.getAttribute('title') ?? el.getAttribute('text') ?? undefined
      const selfCategory = titleAttr
        ? parentCategory
          ? `${parentCategory} > ${titleAttr}`
          : titleAttr
        : parentCategory
      if (xmlUrl) {
        out.push({
          xmlUrl,
          title: titleAttr || undefined,
          category: selfCategory || undefined,
        })
      }
      const children = el.children
      if (children.length > 0) {
        const nested = Array.from(children).filter((c) => c.tagName.toLowerCase() === 'outline')
        if (nested.length > 0) out.push(...walkOutlines(nested, selfCategory))
      }
    }
    return out
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setError(null)
    setResult(null)
    try {
      const text = await file.text()
      const doc = new DOMParser().parseFromString(text, 'text/xml')
      const parseErrors = doc.getElementsByTagName('parsererror')
      if (parseErrors.length > 0) {
        setError(t('importMalformed'))
        setPhase('error')
        return
      }
      const body = doc.querySelector('body')
      if (!body) {
        setError(t('importMalformed'))
        setPhase('error')
        return
      }
      const outlines = Array.from(body.children).filter(
        (c) => c.tagName.toLowerCase() === 'outline'
      )
      const parsed = walkOutlines(outlines, '')
      if (parsed.length === 0) {
        setError(t('importPreviewEmpty'))
        setPhase('error')
        return
      }
      const titles = new Map<string, string>()
      for (const f of parsed) {
        if (f.title) titles.set(f.xmlUrl, f.title)
      }
      setFeeds(parsed)
      setParsedTitles(titles)
      setSelected(new Set(parsed.map((f) => f.xmlUrl)))
      setPhase('parsed')
    } catch {
      setError(t('importMalformed'))
      setPhase('error')
    } finally {
      // Reset the input so the same file can be re-selected after a fix.
      e.target.value = ''
    }
  }

  function toggleOne(url: string) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(url)) next.delete(url)
      else next.add(url)
      return next
    })
  }

  function toggleAll(on: boolean) {
    setSelected(on ? new Set(feeds.map((f) => f.xmlUrl)) : new Set())
  }

  async function onSubmit() {
    const chosen = feeds.filter((f) => selected.has(f.xmlUrl))
    if (chosen.length === 0) return
    if (chosen.length > MAX_FEEDS) {
      setError(t('importOverLimit', { max: MAX_FEEDS }))
      setPhase('error')
      return
    }
    setPhase('submitting')
    setError(null)
    // Backend v1 discards `category`. Strip it client-side so we don't
    // promise a behaviour the API doesn't deliver (Architect flagged this).
    const payload: BulkImportRequest = {
      feeds: chosen.map(({ xmlUrl, title }) => ({ xmlUrl, title })),
    }
    try {
      const r = await api.post<BulkImportResult>('/feeds/bulk', payload)
      setResult(r)
      setPhase('success')
    } catch (e) {
      if (e instanceof ApiError) setError(e.message)
      else setError(t('importOverLimit', { max: MAX_FEEDS }))
      setPhase('error')
    }
  }

  function reset() {
    setFeeds([])
    setSelected(new Set())
    setError(null)
    setResult(null)
    setParsedTitles(new Map())
    setPhase('idle')
  }

  // Group feeds by category for the preview. Flat list when no category
  // info is present (single-level OPML).
  const grouped = new Map<string, OpmlFeedRef[]>()
  for (const f of feeds) {
    const key = f.category ?? ''
    const list = grouped.get(key)
    if (list) list.push(f)
    else grouped.set(key, [f])
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-6 flex items-center gap-2">
        <Rss className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-semibold headline-serif">{t('importPageTitle')}</h1>
      </div>

      <p className="mb-4 text-sm text-muted-foreground">{t('importInstructions')}</p>

      <section
        aria-label={t('importPageTitle')}
        className="rounded-lg border border-border bg-canvas p-5"
      >
        <label htmlFor="opml-file" className="mb-2 block text-sm text-muted-foreground">
          {t('importFileLabel')}
        </label>
        <input
          id="opml-file"
          data-testid="opml-file"
          type="file"
          accept=".opml,.xml,application/xml,text/xml"
          onChange={onFile}
          className="block w-full text-sm text-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-surface file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-foreground hover:file:bg-primary/10"
        />
      </section>

      {error && (
        <p
          role="alert"
          className="mt-4 flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </p>
      )}

      {phase === 'parsed' && feeds.length > 0 && (
        <section className="mt-6 rounded-lg border border-border bg-canvas p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {t('importSelectedCount', {
                selected: selected.size,
                total: feeds.length,
              })}
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => toggleAll(true)}
                className="rounded-md border border-border bg-surface px-3 py-1 text-xs hover:border-primary/40"
              >
                {t('importSelectAll')}
              </button>
              <button
                type="button"
                onClick={() => toggleAll(false)}
                className="rounded-md border border-border bg-surface px-3 py-1 text-xs hover:border-primary/40"
              >
                {t('importSelectNone')}
              </button>
            </div>
          </div>

          <fieldset className="space-y-4">
            <legend className="sr-only">{t('importPageTitle')}</legend>
            {Array.from(grouped.entries()).map(([category, list]) => (
              <div key={category || '__root__'}>
                {category && (
                  <p className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                    {category}
                  </p>
                )}
                <ul className="space-y-1">
                  {list.map((f) => {
                    const isChecked = selected.has(f.xmlUrl)
                    const title = parsedTitles.get(f.xmlUrl) ?? f.title ?? f.xmlUrl
                    return (
                      <li key={f.xmlUrl}>
                        <label className="flex items-start gap-2 rounded-md border border-transparent px-2 py-1.5 hover:border-border hover:bg-surface">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleOne(f.xmlUrl)}
                            aria-label={t('importCheckboxLabel', { title })}
                            className="mt-0.5 h-4 w-4 flex-shrink-0 rounded border-border"
                          />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-sm font-medium">{title}</span>
                            <span className="block truncate text-xs text-muted-foreground">
                              {f.xmlUrl}
                            </span>
                          </span>
                        </label>
                      </li>
                    )
                  })}
                </ul>
              </div>
            ))}
          </fieldset>

          <div className="mt-4 flex justify-end">
            <button
              type="button"
              data-testid="submit-bulk"
              onClick={onSubmit}
              disabled={selected.size === 0}
              className="inline-flex items-center gap-2 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              {t('importSubmit')}
            </button>
          </div>
        </section>
      )}

      {phase === 'submitting' && (
        <p
          role="status"
          className="mt-4 inline-flex items-center gap-2 text-sm text-muted-foreground"
        >
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('importSubmitting')}
        </p>
      )}

      {phase === 'success' && result && (
        <section
          aria-labelledby="import-result-heading"
          className="mt-6 rounded-lg border border-border bg-canvas p-5"
        >
          <h2 id="import-result-heading" className="mb-3 text-base font-semibold">
            {t('importResultHeading')}
          </h2>
          <div className="flex flex-wrap gap-2" data-testid="result-badges">
            <span
              data-testid="badge-created"
              className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {t('importResult.created', { n: result.created })}
            </span>
            {result.skipped_duplicates > 0 && (
              <span
                data-testid="badge-duplicates"
                className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs font-medium text-amber-700 dark:text-amber-300"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                {t('importResult.duplicates', { n: result.skipped_duplicates })}
              </span>
            )}
            {result.failed.length > 0 && (
              <span
                data-testid="badge-failed"
                className="inline-flex items-center gap-1.5 rounded-full border border-destructive/30 bg-destructive/10 px-3 py-1 text-xs font-medium text-destructive"
              >
                <XCircle className="h-3.5 w-3.5" />
                {t('importResult.failed', { n: result.failed.length })}
              </span>
            )}
          </div>

          {result.failed.length > 0 && (
            <ul data-testid="failed-list" className="mt-4 space-y-1 text-sm">
              {result.failed.map((f) => {
                const title = parsedTitles.get(f.url) ?? f.url
                return (
                  <li key={f.url} className="text-destructive">
                    {t('importFailedItem', { title, reason: f.reason })}
                  </li>
                )
              })}
            </ul>
          )}

          <div className="mt-4 flex items-center justify-between">
            <button
              type="button"
              onClick={reset}
              className="text-sm text-muted-foreground underline hover:text-primary"
            >
              {t('importFromFeedsPage')}
            </button>
            <Link
              href="/feeds"
              className="text-sm font-medium text-primary underline hover:no-underline"
            >
              {t('importResult.viewAll')} →
            </Link>
          </div>
        </section>
      )}
    </main>
  )
}
