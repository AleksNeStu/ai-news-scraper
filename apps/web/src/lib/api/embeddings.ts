/**
 * Typed client for the embedding-playground endpoints (Task #34, ADR-022).
 *
 * Endpoints (all JWT-authenticated via the api.{get,post} helpers — the
 * JWT cookie rides on `credentials: 'include'`):
 *   GET  /embeddings/providers    — enumerate LLM factory providers with
 *                                   the boolean capabilities the picker
 *                                   needs (supports_embed,
 *                                   key_configured, etc.).
 *   POST /embeddings/embed        — embed a single text against the
 *                                   picked provider; returns the FULL
 *                                   vector (ADR-022 §22.7).
 *   POST /embeddings/similarity   — embed two texts against one provider
 *                                   and return both vectors + cosine +
 *                                   optional dot_product / euclidean.
 *
 * Key-leak defense (ADR-022 §22.5): the server NEVER returns an API key
 * value, but the response typing for `EmbeddingProvider` is intentionally
 * scoped to the documented fields (id, display_name, supports_embed,
 * requires_own_key, key_configured, dimensions, default_model). The TS
 * type union has no place for a `key` / `api_key` / `secret` field, so
 * even a misbehaving server cannot push a secret into the React tree
 * without breaking the compile.
 */

import { api, ApiError } from '../api'
import type {
  EmbeddingProvidersResponse,
  EmbedRequest,
  EmbedResponse,
  SimilarityRequest,
  SimilarityResponse,
} from '@ai-news-scraper/shared'

/**
 * Enumerate the LLM-factory providers the picker can use.
 *
 * Throws `ApiError` on failure:
 *   - 401 unauthenticated (no JWT cookie sent by the browser).
 */
export async function listEmbeddingProviders(
  init?: RequestInit
): Promise<EmbeddingProvidersResponse> {
  return api.get<EmbeddingProvidersResponse>('/embeddings/providers', init)
}

/**
 * Embed a single text against `provider_id`. The API returns the FULL
 * native-dimension vector — the front-end compresses for display
 * (§22.7) but the raw floats are preserved here for exact comparison
 * research.
 *
 * Throws `ApiError` on failure:
 *   - 401 unauthenticated.
 *   - 422 `provider_unknown` — `provider_id` not in the factory.
 *   - 422 `provider_does_not_support_embedding` — provider has no
 *     `embed()` (e.g. DeepSeek). The picker disables these, but a
 *     request can still slip past the UI.
 *   - 422 `provider_key_missing` — provider requires a key that is not
 *     configured in the deployment env. Surface a "contact your admin"
 *     panel rather than a generic error toast.
 *   - 422 validation — `text` longer than the 8000-char cap.
 */
export async function embedText(req: EmbedRequest): Promise<EmbedResponse> {
  return api.post<EmbedResponse>('/embeddings/embed', req)
}

/**
 * Embed two texts against one provider and return both vectors plus the
 * similarity. Round-trip merges the two embed calls so the front-end
 * renders a comparison view without a second network hop (§22.3).
 *
 * Throws `ApiError` on failure:
 *   - 401 unauthenticated.
 *   - 422 `provider_unknown`.
 *   - 422 `provider_does_not_support_embedding`.
 *   - 422 `provider_key_missing`.
 *   - 422 validation — either text over the 8000-char cap.
 */
export async function computeSimilarity(
  req: SimilarityRequest
): Promise<SimilarityResponse> {
  return api.post<SimilarityResponse>('/embeddings/similarity', req)
}

/** True when the API responded 422 with the
 * `provider_does_not_support_embedding` code (ADR-022 §22.4). Used by
 * the front-end to render "This model doesn't support embeddings" rather
 * than a generic error toast. */
export function isProviderDoesNotSupportEmbedding(e: unknown): boolean {
  return (
    e instanceof ApiError && e.status === 422 && e.code === 'provider_does_not_support_embedding'
  )
}

/** True when the API responded 422 with the `provider_key_missing` code
 * (ADR-022 §22.5). The user-visible copy asks the admin to configure
 * the env-var — the front-end MUST NOT suggest the user supply their
 * own key (v1 has no per-user key path). */
export function isProviderKeyMissing(e: unknown): boolean {
  return e instanceof ApiError && e.status === 422 && e.code === 'provider_key_missing'
}

/** True when the API responded 422 with the `provider_unknown` code
 * (ADR-022 §22.5). Distinct from `provider_does_not_support_embedding`
 * even though both share the 422 status — `provider_unknown` means the
 * id isn't registered at all, whereas `provider_does_not_support_*`
 * means it IS registered but lacks an `embed()` impl. */
export function isProviderUnknown(e: unknown): boolean {
  return e instanceof ApiError && e.status === 422 && e.code === 'provider_unknown'
}