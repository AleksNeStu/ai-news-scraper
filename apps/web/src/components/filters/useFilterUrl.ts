'use client'

/**
 * URL-bound filter state hook.
 *
 * Extracted from `ArticlesToolbar.setParams` (Task #9, original) so the
 * same URL contract is shared across every filter widget on the site.
 * The hook centralises:
 *
 *   - Locale-aware router imports (so consumers don't have to reach
 *     into `@/i18n/navigation` themselves).
 *   - Typed `set` / `append` / `remove` / `reset` / `get` API.
 *   - Auto-reset of `page` to `null` on any filter mutation, so the
 *     user never lands on page 3 of an empty filtered set.
 *
 * URL contract (Task #9 + Task #50):
 *
 *   ?q=<string>           - search query
 *   ?page=<n>             - 1-indexed page number
 *   ?page_size=<n>        - items per page (default 10 on /search, 20 on /articles)
 *   ?source=<domain>      - exact match on Article.source_domain
 *   ?topic=<topic>        - repeatable (?topic=a&topic=b) for multi-select
 *   ?from=<YYYY-MM-DD>    - inclusive lower bound on indexed_at
 *   ?to=<YYYY-MM-DD>      - inclusive upper bound on indexed_at
 *
 * Single-value keys round-trip as `?key=value`; multi-value keys use
 * the same key repeated (`?topic=a&topic=b`), parsed via
 * `getAll(key)`.
 *
 * typedRoutes note: `router.replace` accepts a `Route` literal. The
 * `pathname + qs` we build here is dynamic; cast via `as never` is
 * the same pattern ArticlesToolbar.tsx already uses. typedRoutes
 * only blocks bogus strings, not real ones from `usePathname()`.
 */

import { useCallback } from 'react'
import { usePathname, useRouter, useSearchParams } from '@/i18n/navigation'

export type FilterValue = string | string[] | null

export interface UseFilterUrl {
  /** Replace the value for a single-value key (or null to remove). */
  set(key: string, value: string | null): void
  /** Append a value to a multi-value key (creates the key if absent). */
  append(key: string, value: string): void
  /** Remove a key entirely (or a single value if multi-value). */
  remove(key: string, value?: string): void
  /** Remove every key in the list. */
  reset(keys: readonly string[]): void
  /** Read a single-value key (returns first match for multi-value). */
  get(key: string): string | null
  /** Read all values for a multi-value key. */
  getAll(key: string): string[]
}

const PAGE_KEY = 'page'

export function useFilterUrl(): UseFilterUrl {
  const router = useRouter()
  const pathname = usePathname()
  const search = useSearchParams()

  const buildUrl = useCallback(
    (params: URLSearchParams) => {
      const qs = params.toString()
      return (qs ? `${pathname}?${qs}` : pathname) as never
    },
    [pathname]
  )

  const mutate = useCallback(
    (mutator: (p: URLSearchParams) => void) => {
      const params = new URLSearchParams(search?.toString() ?? '')
      mutator(params)
      // Any filter change resets the page cursor so the user never lands
      // on a page beyond the new result set. Exception: a direct `set(page, ...)`
      // is allowed to leave `page` alone (the mutator handled it).
      if (!params.has('_keep_page')) {
        params.delete(PAGE_KEY)
      }
      params.delete('_keep_page')
      router.replace(buildUrl(params), { scroll: false })
    },
    [router, search, buildUrl]
  )

  const set = useCallback(
    (key: string, value: string | null) => {
      mutate((p) => {
        if (value == null) p.delete(key)
        else p.set(key, value)
      })
    },
    [mutate]
  )

  const append = useCallback(
    (key: string, value: string) => {
      mutate((p) => {
        p.append(key, value)
      })
    },
    [mutate]
  )

  const remove = useCallback(
    (key: string, value?: string) => {
      mutate((p) => {
        if (value === undefined) {
          p.delete(key)
        } else {
          const all = p.getAll(key).filter((v) => v !== value)
          p.delete(key)
          for (const v of all) p.append(key, v)
        }
      })
    },
    [mutate]
  )

  const reset = useCallback(
    (keys: readonly string[]) => {
      mutate((p) => {
        for (const k of keys) p.delete(k)
      })
    },
    [mutate]
  )

  const get = useCallback((key: string) => search?.get(key) ?? null, [search])

  const getAll = useCallback((key: string) => search?.getAll(key) ?? [], [search])

  return { set, append, remove, reset, get, getAll }
}
