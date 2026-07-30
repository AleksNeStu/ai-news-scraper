/**
 * Tests for the embedding-playground API client (Task #34, ADR-022).
 *
 * Coverage:
 *   - `listEmbeddingProviders` GETs `/embeddings/providers` with the
 *     default init (the api.get wrapper adds `credentials: 'include'`).
 *   - `embedText` POSTs `/embeddings/embed` with the request body and
 *     returns the EmbedResponse (FULL vector, dimensions field).
 *   - `computeSimilarity` POSTs `/embeddings/similarity` with the
 *     request body and returns the SimilarityResponse (vectors + cosine
 *     + optional bonus fields).
 *   - The three error-type guards correctly identify the three reserved
 *     422 codes from ADR-022 §22.4 / §22.5, and reject look-alikes
 *     (different status, different code).
 *
 * Key-leak defense (ADR-022 §22.5): the test fixture for
 * `EmbeddingProvider` deliberately excludes any `key`/`api_key`/`secret`
 * field. If a future schema revision accidentally introduces one, the
 * TS compile will fail at the `@ai-news-scraper/shared` boundary
 * (single-source-of-truth) — these tests do not need to assert the
 * negative explicitly, but the fixture mirrors the real shape so a
 * regression here surfaces as a "shape mismatch" rather than a silent
 * leak.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { api, ApiError } from '../api'
import type * as ApiModule from '../api'
import {
  computeSimilarity,
  embedText,
  isProviderDoesNotSupportEmbedding,
  isProviderKeyMissing,
  isProviderUnknown,
  listEmbeddingProviders,
} from './embeddings'
import type { EmbeddingProvider, EmbedResponse, SimilarityResponse } from '@ai-news-scraper/shared'

vi.mock('../api', async () => {
  const actual = await vi.importActual<typeof ApiModule>('../api')
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn() },
  }
})

const getMock = vi.mocked(api.get)
const postMock = vi.mocked(api.post)

const PROVIDERS: EmbeddingProvider[] = [
  {
    id: 'deepseek',
    display_name: 'DeepSeek',
    supports_embed: false,
    requires_own_key: true,
    key_configured: true,
    dimensions: null,
    default_model: null,
  },
  {
    id: 'gemini',
    display_name: 'Google Gemini',
    supports_embed: true,
    requires_own_key: true,
    key_configured: true,
    dimensions: 768,
    default_model: 'text-embedding-004',
  },
  {
    id: 'openrouter',
    display_name: 'OpenRouter',
    supports_embed: true,
    requires_own_key: true,
    key_configured: false, // intentionally false — used in key-missing tests
    dimensions: 1536,
    default_model: 'openai/text-embedding-3-small',
  },
]

const EMBED_RESPONSE: EmbedResponse = {
  provider_id: 'gemini',
  model: 'text-embedding-004',
  dimensions: 768,
  vector: [0.1, 0.2, 0.3, 0.4],
}

const SIM_RESPONSE: SimilarityResponse = {
  provider_id: 'gemini',
  model: 'text-embedding-004',
  dimensions: 768,
  vector_a: [0.1, 0.2, 0.3],
  vector_b: [0.4, 0.5, 0.6],
  cosine_similarity: 0.83,
  dot_product: 0.81,
  euclidean: 0.21,
}

describe('listEmbeddingProviders', () => {
  beforeEach(() => getMock.mockReset())

  it('GETs /embeddings/providers and returns the providers payload', async () => {
    getMock.mockResolvedValueOnce({ providers: PROVIDERS })
    const result = await listEmbeddingProviders()
    expect(getMock).toHaveBeenCalledWith('/embeddings/providers', undefined)
    expect(result).toEqual({ providers: PROVIDERS })
  })

  it('forwards the RequestInit to the underlying fetch wrapper', async () => {
    getMock.mockResolvedValueOnce({ providers: PROVIDERS })
    const init = { signal: new AbortController().signal }
    await listEmbeddingProviders(init)
    expect(getMock).toHaveBeenCalledWith('/embeddings/providers', init)
  })
})

describe('embedText', () => {
  beforeEach(() => postMock.mockReset())

  it('POSTs /embeddings/embed with provider_id + text and returns the response', async () => {
    postMock.mockResolvedValueOnce(EMBED_RESPONSE)
    const result = await embedText({ provider_id: 'gemini', text: 'cat' })
    expect(postMock).toHaveBeenCalledWith('/embeddings/embed', {
      provider_id: 'gemini',
      text: 'cat',
    })
    expect(result).toEqual(EMBED_RESPONSE)
  })

  it('forwards an optional model override when the caller supplies one', async () => {
    postMock.mockResolvedValueOnce(EMBED_RESPONSE)
    await embedText({ provider_id: 'gemini', text: 'cat', model: 'custom-model' })
    expect(postMock).toHaveBeenCalledWith('/embeddings/embed', {
      provider_id: 'gemini',
      text: 'cat',
      model: 'custom-model',
    })
  })
})

describe('computeSimilarity', () => {
  beforeEach(() => postMock.mockReset())

  it('POSTs /embeddings/similarity with the request body and returns the response', async () => {
    postMock.mockResolvedValueOnce(SIM_RESPONSE)
    const result = await computeSimilarity({
      provider_id: 'gemini',
      text_a: 'cat',
      text_b: 'kitten',
    })
    expect(postMock).toHaveBeenCalledWith('/embeddings/similarity', {
      provider_id: 'gemini',
      text_a: 'cat',
      text_b: 'kitten',
    })
    expect(result).toEqual(SIM_RESPONSE)
  })
})

describe('error-type guards (ADR-022 §22.4 / §22.5)', () => {
  // The three reserved 422 codes. The guards MUST identify each one
  // exactly — different status / different code / non-ApiError all
  // resolve to false.
  const cases = [
    {
      name: 'isProviderDoesNotSupportEmbedding',
      fn: isProviderDoesNotSupportEmbedding,
      code: 'provider_does_not_support_embedding',
    } as const,
    {
      name: 'isProviderKeyMissing',
      fn: isProviderKeyMissing,
      code: 'provider_key_missing',
    } as const,
    {
      name: 'isProviderUnknown',
      fn: isProviderUnknown,
      code: 'provider_unknown',
    } as const,
  ] as const

  for (const { name, fn, code } of cases) {
    it(`${name} matches ApiError(422, ${code})`, () => {
      expect(fn(new ApiError(422, 'detail', code))).toBe(true)
    })

    it(`${name} rejects other 422 codes`, () => {
      // Pick a different reserved code per guard so the test exercises
      // the specific `code ===` match rather than a status-only match.
      const other = cases.find((c) => c.code !== code)?.code ?? 'something_else'
      expect(fn(new ApiError(422, 'detail', other))).toBe(false)
    })

    it(`${name} rejects non-422 statuses`, () => {
      expect(fn(new ApiError(401, 'detail', code))).toBe(false)
      expect(fn(new ApiError(500, 'detail', code))).toBe(false)
    })

    it(`${name} rejects non-ApiError values`, () => {
      expect(fn(new Error(code))).toBe(false)
      expect(fn(null)).toBe(false)
      expect(fn(undefined)).toBe(false)
      expect(fn('string')).toBe(false)
    })
  }
})
