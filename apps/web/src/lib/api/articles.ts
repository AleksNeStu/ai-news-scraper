/**
 * Typed client for the articles endpoints.
 *
 * Endpoints (per `.agent/adr/013-tiered-curation.md` + existing list route):
 *   GET /articles?page=&page_size=&tier=&group_by_tier=
 *
 * Tier and `groupByTier` are Task #9 additions — they let the UI filter
 * and group articles by LLM-curated relevance without re-fetching.
 */

import { api, ApiError } from '@/lib/api'
import type { ArticleListResponse, Article, Tier } from '@ai-news-scraper/shared'

export interface ListArticlesOpts {
  page?: number
  pageSize?: number
  tier?: Tier
  groupByTier?: boolean
}

export class ArticlesEmptyError extends ApiError {
  constructor(message = 'No articles returned') {
    super(500, message)
    this.name = 'ArticlesEmptyError'
  }
}

/**
 * Fetch a paginated, optionally tier-filtered articles list.
 *
 *   - `tier` narrows the result to articles in that curation tier.
 *   - `groupByTier` asks the backend to return items pre-grouped by tier
 *     (4 sections, one per tier) — the frontend just renders those groups.
 *
 * Empty list is *not* an error; callers decide what to render.
 */
export async function listArticles(opts: ListArticlesOpts = {}): Promise<ArticleListResponse> {
  const params = new URLSearchParams()
  if (opts.page) params.set('page', String(opts.page))
  if (opts.pageSize) params.set('page_size', String(opts.pageSize))
  if (opts.tier) params.set('tier', opts.tier)
  if (opts.groupByTier) params.set('group_by_tier', 'true')
  const qs = params.toString()
  return api.get<ArticleListResponse>(`/articles${qs ? `?${qs}` : ''}`)
}

/** Convenience: top-N articles in a tier, sorted by score desc. Client-side
 * fallback when the server doesn't expose a tier+limit combo. */
export function topInTier(items: Article[], tier: Tier, limit: number): Article[] {
  return items
    .filter((a) => a.tier === tier && typeof a.score === 'number')
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
    .slice(0, limit)
}
