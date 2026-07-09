/**
 * Typed client for the public shareable-link endpoints (Task #33, ADR-021).
 *
 * Endpoints:
 *   POST /share                  — mint a new share (auth-required).
 *   GET  /s/{token}              — public, unauthenticated read of the
 *                                  shared article projection.
 *
 * Auth:
 *   POST /share rides the existing JWT cookie (the api.post helper sets
 *   credentials: 'include', which is what we want).
 *   GET /s/{token} is intentionally unauthenticated (ADR-021 §21.10 —
 *   "the token IS the credential"), so the public read path uses a raw
 *   fetch with `credentials: 'omit'`. Sending the user's cookie would
 *   not be harmful (the backend doesn't read it on this path) but it
 *   would leak the request origin to whatever the URL points at, which
 *   is unnecessary on a public read.
 */

import { API_BASE, api, ApiError } from '../api'
import type { ShareCreateRequest, ShareResponse, SharedArticleView } from '@ai-news-scraper/shared'

/**
 * Mint a new shareable link for `article_id`. The API returns the
 * server-built full URL; clients do NOT compose the URL themselves
 * (ADR-021 §21.2).
 *
 * Throws `ApiError` on failure (e.g. 401 unauthenticated, 404 article
 * not found, 422 ttl_days out of bounds).
 */
export async function createShare(req: ShareCreateRequest): Promise<ShareResponse> {
  return api.post<ShareResponse>('/share', req)
}

/**
 * Public, unauthenticated read of a shared article. The token is the
 * credential; no cookies, no Authorization header.
 *
 * Throws `ApiError` on failure:
 *   - 404 share_not_found: token unknown or never existed.
 *   - 410 share_expired:   token existed but its `expires_at` has passed
 *                          (ADR-021 §21.7 — distinct from 404).
 *   - 5xx / network:       propagate as `ApiError`.
 */
export async function getSharedArticle(token: string): Promise<SharedArticleView> {
  const res = await fetch(`${API_BASE}/s/${encodeURIComponent(token)}`, {
    method: 'GET',
    credentials: 'omit',
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    let detail = res.statusText
    let code: string | undefined
    try {
      const body = await res.json()
      detail = body.detail || detail
      code = body.code
    } catch {}
    throw new ApiError(res.status, detail, code, res.headers)
  }
  return res.json() as Promise<SharedArticleView>
}

/** True when the API responded with the `share_expired` code (410 Gone). */
export function isShareExpired(e: unknown): boolean {
  return e instanceof ApiError && e.status === 410
}

/** True when the API responded with `share_not_found` or any 404. */
export function isShareNotFound(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404
}
