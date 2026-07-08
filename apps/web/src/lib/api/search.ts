/**
 * Typed client for the /search endpoint.
 *
 * Mirrors the Python `SearchRequest` / `SearchResponse` in
 * `apps/api/api/schemas/search.py` (per the manual-mirror rule in
 * `packages/shared/src/types.ts`).
 *
 * The page-level SearchClient (apps/web/src/app/[locale]/(app)/search)
 * calls this with the URL-derived query + filters.
 */

import { api, ApiError } from '@/lib/api'
import type { SearchRequest as SharedSearchRequest, SearchResponse } from '@ai-news-scraper/shared'

export interface SearchArticlesOpts {
  query: string
  page?: number
  pageSize?: number
  source?: string | null
  topics?: string[]
  dateFrom?: string | null
  dateTo?: string | null
}

export class SearchEmptyError extends ApiError {
  constructor(message = 'No search results') {
    super(500, message)
    this.name = 'SearchEmptyError'
  }
}

/**
 * Fetch a paginated, filtered search result set.
 *
 * Returns the typed `SearchResponse` (results + took_ms + page +
 * page_size + total). Filters are forwarded to the API as the
 * `filters` sub-object; the API currently only honours `source`
 * (topics/date_from/date_to are typed-and-deferred — see Task #50
 * P1-1).
 *
 * Empty list is *not* an error.
 */
export async function searchArticles(opts: SearchArticlesOpts): Promise<SearchResponse> {
  const body: SharedSearchRequest = {
    query: opts.query,
    page: opts.page ?? 1,
    page_size: opts.pageSize ?? 10,
    filters: {
      source: opts.source ?? undefined,
      topics: opts.topics && opts.topics.length > 0 ? opts.topics : undefined,
      date_from: opts.dateFrom ?? undefined,
      date_to: opts.dateTo ?? undefined,
    },
  }
  return api.post<SearchResponse>('/search', body)
}
