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

export interface FeedItem {
  id: ID;
  feed_id: ID;
  article_id: ID | null;
  guid: string;
  title: string;
  url: string;
  fetched_at: string;
}

export interface User {
  id: ID;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
  token: string;
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
