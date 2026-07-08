import { Suspense } from 'react'
import { setRequestLocale } from 'next-intl/server'

import { SearchClient } from '@/app/[locale]/(app)/search/SearchClient'

/**
 * /search page (Task #32 + Task #49).
 *
 * Server Component shell that:
 *   1. Validates the active locale (already done by [locale]/layout.tsx,
 *      but we still call setRequestLocale to be safe under static export).
 *   2. Reads the current searchParams (q, page, source, topic[], from, to).
 *   3. Hands the parsed values to <SearchClient> wrapped in a
 *      <Suspense> boundary (Next 15.5 prerender rule: any client
 *      component that calls useSearchParams() needs one).
 *
 * All actual search logic (debounce, fetch, states) lives in
 * SearchClient.tsx. This file is just the SSR shell.
 */

export const dynamic = 'force-dynamic'

interface SearchPageProps {
  params: Promise<{ locale: string }>
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

function firstString(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) return value[0] ?? null
  return value ?? null
}

function toNumber(value: string | null, fallback: number): number {
  if (value == null) return fallback
  const n = Number(value)
  return Number.isFinite(n) && n > 0 ? n : fallback
}

export default async function SearchPage({ params, searchParams }: SearchPageProps) {
  const { locale: rawLocale } = await params
  const locale = rawLocale as 'en' | 'ru'
  setRequestLocale(locale)

  const sp = await searchParams
  const initialQuery = firstString(sp.q) ?? ''
  const initialPage = toNumber(firstString(sp.page), 1)
  const initialPageSize = toNumber(firstString(sp.page_size), 10)
  const initialSource = firstString(sp.source)
  const initialTopics = Array.isArray(sp.topic) ? sp.topic : sp.topic ? [sp.topic] : []
  const initialFrom = firstString(sp.from)
  const initialTo = firstString(sp.to)

  return (
    <Suspense>
      <SearchClient
        initialQuery={initialQuery}
        initialPage={initialPage}
        initialPageSize={initialPageSize}
        initialSource={initialSource}
        initialTopics={initialTopics}
        initialFrom={initialFrom}
        initialTo={initialTo}
      />
    </Suspense>
  )
}
