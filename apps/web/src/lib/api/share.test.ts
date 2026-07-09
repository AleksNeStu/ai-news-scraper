/**
 * Tests for the share API client (Task #33, ADR-021).
 *
 * Covers the two contracts the UI relies on:
 *   - `createShare` POSTs `{ article_id, ttl_days }` and returns the
 *     server-built URL untouched (the client must NOT compose the URL
 *     itself; ADR-021 §21.2).
 *   - `getSharedArticle` hits `GET /s/{token}` with `credentials: 'omit'`
 *     (the token IS the credential; ADR-021 §21.10) and surfaces the
 *     dedicated `code` from 404/410 responses for the helpers
 *     `isShareNotFound` / `isShareExpired`.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api, ApiError, API_BASE } from '../api'
import { createShare, getSharedArticle, isShareExpired, isShareNotFound } from './share'
import type { ShareResponse, SharedArticleView } from '@ai-news-scraper/shared'
import type * as ApiModule from '../api'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof ApiModule>('../api')
  return {
    ...actual,
    api: { post: vi.fn(), get: vi.fn() },
  }
})

const postMock = vi.mocked(api.post)

describe('createShare', () => {
  beforeEach(() => postMock.mockReset())

  it('POSTs /share with article_id and ttl_days and returns the server URL', async () => {
    const share: ShareResponse = {
      token: 'abc123',
      url: `${API_BASE}/s/abc123`,
      expires_at: '2026-08-08T00:00:00Z',
      article_id: 'art1',
    }
    postMock.mockResolvedValueOnce(share)

    const result = await createShare({ article_id: 'art1', ttl_days: 30 })

    expect(postMock).toHaveBeenCalledWith('/share', { article_id: 'art1', ttl_days: 30 })
    expect(result).toEqual(share)
    expect(result.url).toBe(share.url)
  })

  it('omits ttl_days when caller does not supply it (backend default = 30)', async () => {
    const share: ShareResponse = {
      token: 'xyz',
      url: 'https://example.test/s/xyz',
      expires_at: '2026-08-08T00:00:00Z',
      article_id: 'art1',
    }
    postMock.mockResolvedValueOnce(share)

    await createShare({ article_id: 'art1' })

    expect(postMock).toHaveBeenCalledWith('/share', { article_id: 'art1' })
  })
})

describe('getSharedArticle', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  function makeFetchResponse(status: number, body: unknown): Response {
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? 'OK' : status === 404 ? 'Not Found' : 'Gone',
      json: vi.fn().mockResolvedValue(body),
      headers: new Headers(),
    } as unknown as Response
  }

  it('GETs /s/{token} with credentials omitted and returns the parsed payload', async () => {
    const view: SharedArticleView = {
      article_id: 'art1',
      title: 'A headline',
      summary: 'A summary',
      topics: ['ai', 'news'],
      source_url: 'https://example.com/article',
      published_at: '2026-07-08T00:00:00Z',
      shared_at: '2026-07-09T00:00:00Z',
      expires_at: '2026-08-08T00:00:00Z',
    }
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(makeFetchResponse(200, view))

    const result = await getSharedArticle('tok-xyz')

    expect(fetchSpy).toHaveBeenCalledWith(`${API_BASE}/s/tok-xyz`, {
      method: 'GET',
      credentials: 'omit',
      headers: { Accept: 'application/json' },
    })
    expect(result).toEqual(view)
  })

  it('throws ApiError(404, share_not_found) when token is unknown', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        makeFetchResponse(404, { detail: 'No such share', code: 'share_not_found' })
      )

    await expect(getSharedArticle('missing')).rejects.toBeInstanceOf(ApiError)
    try {
      await getSharedArticle('missing')
      throw new Error('expected reject')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect(e).toMatchObject({ status: 404, code: 'share_not_found' })
    }
    expect(isShareNotFound(new ApiError(404, '', 'share_not_found'))).toBe(true)
    fetchSpy.mockRestore()
  })

  it('throws ApiError(410, share_expired) when token has expired', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(
        makeFetchResponse(410, { detail: 'This share link has expired', code: 'share_expired' })
      )

    await expect(getSharedArticle('expired')).rejects.toBeInstanceOf(ApiError)
    try {
      await getSharedArticle('expired')
      throw new Error('expected reject')
    } catch (e) {
      expect(e).toBeInstanceOf(ApiError)
      expect(e).toMatchObject({ status: 410, code: 'share_expired' })
    }
    expect(isShareExpired(new ApiError(410, '', 'share_expired'))).toBe(true)
    fetchSpy.mockRestore()
  })
})
