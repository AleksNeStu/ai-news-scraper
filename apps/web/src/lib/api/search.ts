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
import type {
  FacetsResponse,
  SearchRequest as SharedSearchRequest,
  SearchResponse,
} from '@ai-news-scraper/shared'

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

/**
 * Fetch per-dimension facet aggregations for the current user's library.
 *
 * Hits `GET /search/facets`. No request body. `init.signal` is forwarded
 * so React Query / the FilterPanel mount can cancel an in-flight request
 * on unmount or when the user-id changes.
 *
 * Server side is Redis-cached (60s TTL, keyed on `facets:{user_id}`);
 * the response also ships `Cache-Control: private, max-age=60`. To match
 * server freshness at the consumer layer, configure
 * `staleTime: 60_000` on the consuming `useQuery` (or call once per page
 * load in a mount-only effect).
 *
 * Empty library returns `{ sources: [], topics: [], date_range: { min: null, max: null } }`
 * with HTTP 200 — this is NOT an error. UI should render the "empty
 * library" placeholder when both date bounds are null.
 *
 * Throws `ApiError` (from `@/lib/api`) on non-2xx.
 */
export async function searchFacets(
  init?: RequestInit & { signal?: AbortSignal }
): Promise<FacetsResponse> {
  return api.get<FacetsResponse>('/search/facets', init)
}
