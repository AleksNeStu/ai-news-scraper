/**
 * Typed client for the AI Brief digest endpoints.
 *
 * Endpoints (per `.agent/adr/012-ai-brief.md` §12.2 + M4 unsubscribe):
 *   GET  /digest/today
 *   GET  /digest/{for_date}
 *   GET  /digest?cursor=...&limit=...
 *   POST /digest/{digest_id}/unsubscribe   (public — token in form body)
 *
 * Auth:
 *   /digest/* GETs require the existing JWT cookie.
 *   /digest/{id}/unsubscribe is public; the signed `token` (JWT) is the
 *   credential. NO Authorization header, NO cookie — RFC 8058 §3.2 one-click.
 */

import { API_BASE, api, ApiError } from '../api'
import type { Digest, DigestListResponse, UnsubscribeResponse } from '@ai-news-scraper/shared'

/** 404 with `code === "digest_disabled"` — backend `digest_enabled = false`. */
export class DigestDisabledError extends ApiError {
  constructor(message = 'Daily briefs are temporarily unavailable') {
    super(404, message, 'digest_disabled')
    this.name = 'DigestDisabledError'
  }
}

/** 404 with no special code (or `code === "digest_not_found"`) — no digest generated yet. */
export class DigestNotFoundError extends ApiError {
  constructor(message = 'No digest for that date') {
    super(404, message, 'digest_not_found')
    this.name = 'DigestNotFoundError'
  }
}

/**
 * Inspect a 404 from /digest/* and return the right typed error. M6:
 * backend disables the endpoint with the same 404 but a distinct
 * `code` so the UI can show "temporarily unavailable" vs. "no brief yet".
 */
function classifyDigestNotFound(e: ApiError, fallbackMsg?: string): never {
  if (e.code === 'digest_disabled') throw new DigestDisabledError(e.message)
  throw new DigestNotFoundError(fallbackMsg ?? e.message)
}

/** Today (UTC) as `YYYY-MM-DD`. */
export function todayUtc(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Today's digest for the caller. 404 throws `DigestNotFoundError` or `DigestDisabledError`. */
export async function getTodayDigest(): Promise<Digest> {
  try {
    return await api.get<Digest>('/digest/today')
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) classifyDigestNotFound(e)
    throw e
  }
}

/** Digest for a specific UTC date (`YYYY-MM-DD`). */
export async function getDigest(forDate: string): Promise<Digest> {
  try {
    return await api.get<Digest>(`/digest/${encodeURIComponent(forDate)}`)
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) classifyDigestNotFound(e)
    throw e
  }
}

/** Cursor-paginated history. `next_cursor === null` when no more pages. */
export async function listDigests(cursor?: string, limit = 20): Promise<DigestListResponse> {
  const params = new URLSearchParams()
  if (cursor) params.set('cursor', cursor)
  params.set('limit', String(limit))
  const qs = params.toString()
  return api.get<DigestListResponse>(`/digest?${qs}`)
}

/**
 * POST one-click unsubscribe (RFC 8058). Public endpoint — the signed JWT
 * `token` is the credential. Sends `application/x-www-form-urlencoded`
 * (per ADR-012 §12.6) so we don't go through the JSON-only `api.post` wrapper.
 */
export async function unsubscribeDigest(
  digestId: string,
  token: string
): Promise<UnsubscribeResponse> {
  const body = new URLSearchParams({ token }).toString()
  const res = await fetch(`${API_BASE}/digest/${encodeURIComponent(digestId)}/unsubscribe`, {
    method: 'POST',
    credentials: 'omit',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!res.ok) {
    let detail = res.statusText
    let code: string | undefined
    try {
      const j = await res.json()
      detail = j.detail || detail
      code = j.code
    } catch {}
    throw new ApiError(res.status, detail, code)
  }
  return res.json() as Promise<UnsubscribeResponse>
}
