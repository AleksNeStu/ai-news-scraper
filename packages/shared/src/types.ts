/**
 * Shared types between apps/api (Python) and apps/web (TypeScript).
 * Keep this file framework-agnostic. Manual mirror of Pydantic schemas in
 * apps/api/api/schemas/*.py — keep them in sync.
 */

export type ID = string;

/** Curation tier for an article (Task #9). Derived from `Article.score`
 * via `tier_from_score`; mirrored from the Python `Literal[...]` in
 * `apps/api/api/schemas/article.py`. */
export type Tier = 'must_read' | 'recommended' | 'worth_a_look' | 'low_priority';

export interface Article {
  id: ID;
  url: string;
  headline: string;
  body: string;
  summary: string;
  topics: string[];
  source_domain: string;
  publish_date: string | null;
  indexed_at: string;
  user_id: ID | null;
  /** LLM relevance score, 0.0..1.0. `null` when never scored. */
  score: number | null;
  /** Curation tier derived from `score`; `null` when never scored. */
  tier: Tier | null;
  /** When `score` was last computed (ISO 8601 UTC); `null` when never scored. */
  scored_at: string | null;
}

/** Web-side alias for the API's `ArticleOut` Pydantic schema. Identical
 * shape to `Article`; kept distinct so web code can express "I'm
 * expecting an Article from a `/articles/...` endpoint" without
 * inventing a new type. */
export type ArticleOut = Article;

export interface ArticleListResponse {
  items: Article[];
  total: number;
  page: number;
  page_size: number;
}

export interface ScrapeRequest {
  url: string;
}

export interface BatchScrapeRequest {
  urls: string[];
}

export interface SearchRequest {
  query: string;
  /** 1-indexed page number. Defaults to 1. */
  page?: number;
  /** Items per page. Defaults to 10; max 100. */
  page_size?: number;
  /**
   * Deprecated synonym for `page_size`. If both are sent, `page_size`
   * wins. Mirrors the Python `SearchRequest.top_k` in
   * `apps/api/api/schemas/search.py`.
   */
  top_k?: number;
  filters?: SearchFilters;
}

export interface SearchFilters {
  source?: string;
  topics?: string[];
  date_from?: string;
  date_to?: string;
}

export interface SearchResult {
  article: Article;
  score: number;
  highlights?: string[];
}

export interface SearchResponse {
  results: SearchResult[];
  took_ms: number;
  /** 1-indexed page number that produced `results`. */
  page: number;
  /** Items per page used for `results`. */
  page_size: number;
  /** Total number of hits matching the query (across all pages). */
  total: number;
}

/** A single (value, count) pair returned by `GET /search/facets` for one
 * bucket of a dimension (e.g. one source domain, one topic). Mirrors the
 * Pydantic `FacetCount` in `apps/api/api/schemas/search.py` (Task #53,
 * ADR-020). */
export interface FacetCount {
  /** Bucket value as a string (source domain, topic slug, etc.). */
  value: string;
  /** Number of articles in the user's library that fall in this bucket. */
  count: number;
}

/** Min / max `indexed_at` across the user's library, returned by
 * `GET /search/facets` so the web `DateRangeFilter` can clamp its
 * inputs to the populated range. `null` on either bound means the
 * library is empty (the router returns `{min: null, max: null}` in
 * that case — see ADR-020 §20.4). ISO 8601 UTC strings when set. */
export interface FacetDateRange {
  min: string | null;
  max: string | null;
}

/** Response body for `GET /search/facets`. One list per discrete
 * dimension (sources, topics) plus a single date range covering the
 * whole library. Mirrors the Pydantic `FacetsResponse` in
 * `apps/api/api/schemas/search.py` (Task #53, ADR-020). */
export interface FacetsResponse {
  /** Counts of articles per `source_domain`. */
  sources: FacetCount[];
  /** Counts of articles per topic. Each `Article.topics` element
   * contributes to exactly one bucket (the `value` is the topic
   * string, not the article id), so an article tagged
   * `['ai','ml']` is counted once under `ai` and once under `ml`. */
  topics: FacetCount[];
  /** Min / max `indexed_at` across the user's library. */
  date_range: FacetDateRange;
  /** Names of dimensions whose aggregation raised inside
   * `aggregate_facets` and were replaced with empty / null values
   * (Task #53 Devil M-2). Always emitted by the API; empty array on
   * the happy path. The route returns 200 even on partial failure so
   * the filter UI degrades gracefully; the front-end can show a
   * "partial facets" banner by checking this list is non-empty.
   * Possible entries: `"sources"`, `"topics"`, `"date_range"`.
   *
   * Required (not optional) because the API contract guarantees its
   * presence and the partial-failure signal is load-bearing — callers
   * that omit it from a typed literal will get a TS error, which is
   * the correct behavior. (Initial Task #57 review shipped this as
   * optional to avoid breaking `SearchClient.test.tsx`'s pre-existing
   * literal; the fixture has since been updated to include the
   * field, so the optional marker was lifted in the follow-up.) */
  degraded_dimensions: string[];
}

export interface Feed {
  id: ID;
  user_id: ID;
  feed_url: string;
  title: string;
  description: string | null;
  last_polled: string | null;
  active: boolean;
  item_count: number;
  created_at: string;
}

/** Web-side alias for the API's `FeedOut` Pydantic schema. */
export type FeedOut = Feed;

export interface FeedListResponse {
  items: Feed[];
  total: number;
}

export interface FeedItem {
  id: ID;
  feed_id: ID;
  article_id: ID | null;
  guid: string;
  title: string;
  url: string;
  fetched_at: string;
}

/** Web-side alias for the API's `FeedItemOut` Pydantic schema. */
export type FeedItemOut = FeedItem;

export interface User {
  id: ID;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  token: string;
}

/** Payload for `POST /auth/login`. Mirrors Pydantic `UserLogin`
 * (`apps/api/api/schemas/auth.py`): `email: EmailStr`, `password: str`. */
export interface LoginRequest {
  email: string;
  password: string;
}

/** Payload for `POST /auth/register`. Mirrors Pydantic `UserCreate`
 * (`apps/api/api/schemas/auth.py`): `email: EmailStr`,
 * `password: str` (min 8, max 128 on the server). */
export interface RegisterRequest {
  email: string;
  password: string;
}

export interface ApiError {
  detail: string;
  code?: string;
}

// ============================================================================
// AI Brief (Task #8)
// ============================================================================
//
// Daily digest: APScheduler cron at 08:00 user-local fetches the last 24h of
// the user's articles, clusters them by topic via LLM, and produces a 500-word
// overall summary + 200-word section per cluster. Surfaced in-app as a
// Notification and optionally emailed (RFC 8058 compliant). See
// `.agent/adr/012-ai-brief.md`.

/** Delivery state for a generated digest. */
export type DigestStatus = "pending" | "notified" | "emailed" | "failed";

/** One LLM-generated topic cluster inside a digest. */
export interface DigestSection {
  /** Stable identifier; slug of `topic`. */
  cluster_id: ID;
  /** Human-readable cluster name (e.g. "EU AI Act amendments"). */
  topic: string;
  /** ~200-word brief summarizing the cluster. */
  summary: string;
  /** Article IDs belonging to this cluster (ordered by relevance desc). */
  article_ids: ID[];
  /** Rank within the digest (1 = top cluster). */
  rank: number;
}

/** One full daily digest for one user on one date. */
export interface Digest {
  id: ID;
  /** Owning user. */
  user_id: ID;
  /** UTC date the digest covers, `YYYY-MM-DD`. */
  for_date: string;
  /** ~500-word summary spanning all clusters. */
  overall_summary: string;
  /** Clustered sections, ordered by `rank` ascending. */
  sections: DigestSection[];
  /** When the brief was generated (UTC, ISO 8601). */
  generated_at: string;
  /** Delivery state — see `DigestStatus`. */
  delivery_status: DigestStatus;
  /** SMTP `Message-Id` (RFC 5322) once email has been sent; else `null`. */
  email_message_id: string | null;
}

/** Cursor-paginated digest list (e.g. `GET /digest?cursor=...`). */
export interface DigestListResponse {
  digests: Digest[];
  /** Opaque cursor returned as `null` when no more pages. */
  next_cursor: string | null;
}

/** In-app notification surfaced to the user. */
export interface Notification {
  id: ID;
  user_id: ID;
  /** Event kind. `brief_ready` includes a `digest_id`; `system` is generic. */
  kind: "brief_ready" | "brief_failed" | "system";
  /** Headline ≤ 80 chars. */
  title: string;
  /** Body preview ≤ 280 chars. */
  preview: string;
  /** Optional in-app link (e.g. `/dashboard/brief/2026-06-29`). `null` for `system`. */
  href: string | null;
  /** Digest ID when `kind === "brief_ready"`. */
  digest_id: ID | null;
  /** Whether the user has read this notification. */
  read: boolean;
  /** ISO 8601 UTC. */
  created_at: string;
  /** ISO 8601 UTC; `null` until `read === true`. */
  read_at: string | null;
}

/** Payload handed from the digest worker to the SMTP transport.
 * Carries `recipient_user_id` only — the raw email is resolved server-side
 * in the SMTP transport and never crosses the worker→transport boundary,
 * so retry queues / log lines / intermediate exception tracebacks cannot
 * leak it (ADR-012 §12.7). */
export interface EmailDigestPayload {
  recipient_user_id: ID;
  digest_id: ID;
  for_date: string;
  /** RFC 8058 plain-text alt body (multipart/alternative). */
  text_body: string;
  /** RFC 8058 HTML body. */
  html_body: string;
  /** Absolute URL for one-click unsubscribe (signed with JWT). */
  list_unsubscribe_url: string;
  /** Pre-formatted `List-Unsubscribe` header value (`<mailto:...>, <url:...>`). */
  list_unsubscribe_header: string;
}

/** JWT payload for one-click unsubscribe (RFC 8058 §3.2). The signed token
 * is the credential — no cookie, no `Authorization` header. Minted with a
 * `jti` (unique per token) and a `kid` header; verified with replay
 * protection against `digest_unsubscribe_log.jwt_id`. See ADR-012 §12.7. */
export interface UnsubscribeTokenClaims {
  digest_id: ID;
  user_id: ID;
  action: "unsubscribe";
  /** Unique per token; replay protection key. UUIDv4. */
  jti: string;
  /** Issued-at, unix seconds. */
  iat: number;
  /** Expiry, unix seconds. Recommend now + 30 days. */
  exp: number;
}

/** Response body for `POST /digest/{digest_id}/unsubscribe`. Always 200
 * with a body (never 204) so a confirmation page can read the result. */
export interface UnsubscribeResponse {
  /** True if this call flipped `email_digest_enabled` to false; false if
   * the user was already unsubscribed (idempotent replay path). */
  unsubscribed: boolean;
  /** ISO 8601 UTC. On replay, this is the original `consumed_at`, not now. */
  at: string;
}

// ============================================================================
// Public shareable article links (Task #33, ADR-021)
// ============================================================================
//
// `POST /share` mints an opaque, unguessable token; the API responds with the
// full URL a user can paste into a chat / email. `GET /s/{token}` is the
// public, unauthenticated read endpoint that serves the article's public
// projection (`SharedArticleView`). See `.agent/adr/021-*` for the threat
// model and the explicit allow-list rationale.

/** Payload for `POST /share`. Mirrors the Pydantic `ShareCreateRequest`
 * (`apps/api/api/schemas/share.py`): `article_id: UUID`,
 * `ttl_days: int` (1..365, default 30). */
export interface ShareCreateRequest {
  /** Article to publish a snapshot of. */
  article_id: ID;
  /** Lifetime in days (1..365). Defaults to 30. */
  ttl_days?: number;
}

/** Response body for `POST /share`. The `url` is server-built from
 * `request.base_url` + the new token; clients do not compose it. Mirrors
 * the Pydantic `ShareResponse` in `apps/api/api/schemas/share.py`. */
export interface ShareResponse {
  /** Opaque, unguessable token (>= 256 bits entropy, `secrets.token_urlsafe(32)`). */
  token: string;
  /** Full shareable URL (origin + `/s/{token}`); built server-side. */
  url: string;
  /** ISO 8601 UTC expiry. Always non-null in v1. */
  expires_at: string;
  /** Article the snapshot is bound to. */
  article_id: ID;
}

/** Unauthenticated public projection of an article, served by
 * `GET /s/{token}`. The field set is an explicit allow-list — every field
 * not listed here is intentionally excluded. See ADR-021 §21.3 for the
 * exclusion rationale (no `owner_id`, no `embedding_vector`, no raw body,
 * no internal metadata). Mirrors the Pydantic `SharedArticleView` in
 * `apps/api/api/schemas/share.py`. */
export interface SharedArticleView {
  article_id: ID;
  title: string;
  /** LLM-generated summary; `null` when never summarised. */
  summary: string | null;
  /** Topic tags, deduped and sorted. */
  topics: string[];
  /** Original source URL; `null` for scraped-but-sourceless rows. */
  source_url: string | null;
  /** Original publication timestamp (ISO 8601 UTC); `null` if unknown. */
  published_at: string | null;
  /** When the share was created (ISO 8601 UTC). Distinct from visit time. */
  shared_at: string;
  /** When the share expires (ISO 8601 UTC). Always non-null in v1. */
  expires_at: string;
}

// ============================================================================
// Embedding playground (Task #34, ADR-022)
// ============================================================================
//
// Internal tool: a logged-in user pastes text, picks an embedding model, sees
// the vector and a side-by-side cosine similarity. Surfaces the LLM factory's
// provider inventory (ADR-011) without forcing the web app to hard-code the
// list. See `.agent/adr/022-embedding-playground.md` for the locked
// decisions (provider enumeration, full-vector API, 422-not-500 for unsupported
// providers, key gating, rate limit, no-cache, auth posture).

/** One provider entry returned by `GET /embeddings/providers`. The list is
 * derived from the LLM factory at `apps/api/api/services/llm/__init__.py`
 * (ADR-011 §11.4) — the API is the source of truth; the front-end picker is
 * driven entirely by this payload. Mirrors the Pydantic `EmbeddingProvider`
 * in `apps/api/api/schemas/embeddings.py`. */
export interface EmbeddingProvider {
  /** Stable string identifier matching the factory key (e.g. `"deepseek"`,
   * `"gemini"`, `"openrouter"`). Echoed back in `EmbedRequest.provider_id`
   * and `SimilarityRequest.provider_id`. */
  id: string;
  /** Human-readable name for the provider picker UI (e.g. `"DeepSeek"`,
   * `"Google Gemini"`, `"OpenRouter"`). */
  display_name: string;
  /** Whether this provider implements the `embed()` contract (ADR-011
   * §11.1). `false` for DeepSeek — its `embed()` raises
   * `NotImplementedError` (see `apps/api/api/services/llm/deepseek.py:19-22`).
   * The front-end picker MUST disable + annotate these entries, and any
   * call referencing them is rejected with 422 (not 500). */
  supports_embed: boolean;
  /** Whether this provider needs its own API key separate from the
   * project's default LLM key. When `true`, `key_configured` MUST also be
   * `true` for calls to succeed. */
  requires_own_key: boolean;
  /** Whether the provider's key is configured in the deployment env. The
   * key value itself is NEVER returned in this payload — even to an
   * authenticated user (ADR-022 §22.5). When `false` and the provider is
   * selected, the API responds 422 with `provider_key_missing`. */
  key_configured: boolean;
  /** Native output dimension for the provider's default embed model. The
   * API always returns the FULL vector (no truncation), so the front-end
   * can compress for display while keeping the raw values available for
   * exact comparison. `null` when `supports_embed === false` (DeepSeek). */
  dimensions: number | null;
  /** Default embed model identifier the provider will use when no override
   * is supplied. Surfaced in the picker so the user knows what they're
   * testing against. `null` when `supports_embed === false`. */
  default_model: string | null;
}

/** Response body for `GET /embeddings/providers`. Mirrors the Pydantic
 * `EmbeddingProvidersResponse` in `apps/api/api/schemas/embeddings.py`. */
export interface EmbeddingProvidersResponse {
  providers: EmbeddingProvider[];
}

/** Payload for `POST /embeddings/embed`. The API re-embeds on every call
 * (no server-side cache for v1, ADR-022 §22.8) so the user always sees a
 * live vector from the chosen model — caching would defeat the
 * "compare across providers" use case if a provider silently updated its
 * model. Mirrors the Pydantic `EmbedRequest` in
 * `apps/api/api/schemas/embeddings.py`. */
export interface EmbedRequest {
  /** Provider id from `EmbeddingProvidersResponse` (e.g. `"gemini"`).
   * Must satisfy `supports_embed === true` AND
   * `(requires_own_key === false || key_configured === true)`. Otherwise
   * the API responds 422 (never 500). */
  provider_id: string;
  /** Free-form input text. Server-side cap matches the existing embedder
   * path in `apps/api/api/services/embedder.py:31` (texts truncated to
   * 8000 chars). */
  text: string;
  /** Optional model override; falls back to the provider's `default_model`.
   * `null`/unset means "use the provider default". */
  model?: string | null;
}

/** Response body for `POST /embeddings/embed`. The vector is the FULL
 * native-dimension output (ADR-022 §22.7) — no API-side truncation.
 * Truncation is a display concern owned by the front-end. Mirrors the
 * Pydantic `EmbedResponse` in `apps/api/api/schemas/embeddings.py`. */
export interface EmbedResponse {
  provider_id: string;
  /** Model that produced the vector. Echoes the requested model or the
   * provider's `default_model` when the request omitted one. */
  model: string;
  /** Native output dimension (matches `EmbeddingProvider.dimensions`). */
  dimensions: number;
  /** Full embedding vector. Length equals `dimensions`. Front-end may
   * compress to hex + first-8-dims for display, but the raw floats are
   * kept here for exact comparison research. */
  vector: number[];
}

/** Payload for `POST /embeddings/similarity`. Two texts against one
 * provider — the comparison is always provider-scoped (ADR-022 §22.3).
 * Cross-provider similarity is out of scope for v1 and can be added by
 * calling `/embeddings/embed` twice and computing client-side. Mirrors
 * the Pydantic `SimilarityRequest` in
 * `apps/api/api/schemas/embeddings.py`. */
export interface SimilarityRequest {
  provider_id: string;
  text_a: string;
  text_b: string;
  /** Optional model override; falls back to the provider's `default_model`. */
  model?: string | null;
}

/** Response body for `POST /embeddings/similarity`. Returns both vectors
 * AND the cosine similarity so the front-end can render a comparison view
 * without a second round-trip. `dot_product` and `euclidean` are bonus
 * fields (ADR-022 §22.3) — present when the implementation surfaces them,
 * omitted otherwise. Mirrors the Pydantic `SimilarityResponse` in
 * `apps/api/api/schemas/embeddings.py`. */
export interface SimilarityResponse {
  provider_id: string;
  /** Model that produced both vectors. */
  model: string;
  /** Native output dimension (matches `EmbeddingProvider.dimensions`). */
  dimensions: number;
  /** Full embedding for `text_a`. */
  vector_a: number[];
  /** Full embedding for `text_b`. */
  vector_b: number[];
  /** Cosine similarity in `[-1, 1]`. The default and required metric —
   * every provider in ADR-011 §11.7 emits unit-normalised vectors, so the
   * cosine result is also the dot product of the normalised vectors. */
  cosine_similarity: number;
  /** Optional dot product (raw, un-normalised). Surfaced when the
   * implementation computes it cheaply; `null` if absent. */
  dot_product?: number | null;
  /** Optional Euclidean distance between the two vectors. Surfaced when
   * the implementation computes it cheaply; `null` if absent. */
  euclidean?: number | null;
}

// ============================================================================
// OPML bulk import (Task #35, ADR-024)
// ============================================================================
//
// User uploads an OPML file; the web client parses it via DOMParser, then POSTs
// the extracted feed references to `POST /feeds/bulk`. Backend dedupes against
// existing feeds, validates each URL via `FeedParser`, creates the survivors
// in one statement, and returns a partial-success summary. See ADR-024 for
// dedup strategy, partial-success semantics, parse-failure policy, OPML
// parsing location (browser), and scheduler integration.

/** Single feed reference parsed from OPML by the web client.
 * Mirrors the Pydantic `OpmlFeedRef` in `apps/api/api/schemas/feed.py`. */
export interface OpmlFeedRef {
  /** RSS/Atom feed URL. Required; validated server-side as `HttpUrl`. */
  xmlUrl: string;
  /** Display title from the OPML `<outline>` `title`/`text` attr; optional. */
  title?: string;
  /** OPML outline folder (e.g. "Tech > AI"). Discarded by the v1 backend;
   * plumbed through for forward-compat with v2 category grouping. */
  category?: string;
}

/** Body of `POST /feeds/bulk`. The server caps `feeds.length` at 500 and
 * rejects empty arrays with 422. Mirrors the Pydantic `BulkImportRequest`
 * in `apps/api/api/schemas/feed.py`. */
export interface BulkImportRequest {
  feeds: OpmlFeedRef[];
}

/** One feed in the bulk import that could not be created (parse failure,
 * network error, or DB error). Mirrors the Pydantic `BulkImportFailure`
 * in `apps/api/api/schemas/feed.py`. */
export interface BulkImportFailure {
  url: string;
  /** Backend-provided, generic — does not leak internal exception text. */
  reason: string;
}

/** Response body for `POST /feeds/bulk`. Always HTTP 200 on shape-valid
 * input; per-item failures land in `failed` rather than failing the batch
 * (ADR-024 §24.2). Mirrors the Pydantic `BulkImportResult` in
 * `apps/api/api/schemas/feed.py`. */
export interface BulkImportResult {
  /** Number of new `Feed` rows created in this call. */
  created: number;
  /** URLs in the request that already existed for this user; no-op for them. */
  skipped_duplicates: number;
  /** Per-URL failures (parse error, network error, DB error). */
  failed: BulkImportFailure[];
}

// ============================================================================
// Topic extraction (ADR-026)
// ============================================================================
//
// Wire shape for the `ArticleTopicExtractor` service
// (`apps/api/api/services/topic_extractor.py`). The service returns
// `string[]` (sanitized, deduped, byte-stable sorted); these are the raw
// LLM-call shapes the service validates against before the sanitize pipeline.

/** TopicExtractionResult — wire shape for the TopicExtractor service
 * (apps/api/api/schemas/topic.py). The service returns `list<string>`
 * after sanitization; this is the raw LLM-call shape.
 *
 * No breaking change to existing types.
 */
export interface ExtractedTopic {
  /** Lowercase-kebab tag, matches ``^[a-z0-9][a-z0-9-]{0,62}$``. */
  tag: string;
  /** LLM-reported confidence in [0.0, 1.0]. */
  confidence: number;
}

export interface TopicExtractionResult {
  topics: ExtractedTopic[];
}
