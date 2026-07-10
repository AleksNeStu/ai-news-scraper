# Task #53 — Acceptance Criteria: `GET /search/facets` endpoint

**Scope.** New endpoint `apps/api/api/routers/search.py:facets` returning
`FacetsResponse{sources: list[FacetCount], topics: list[FacetCount],
date_range: {min, max}}`. Pure SQL aggregation on `Article` for the
**current** `user_id`, one query per facet dimension. Redis 60s cache
keyed by `user_id`; response carries `Cache-Control: private, max-age=60`.
Used by `SourceFilter` / `TopicMultiSelect` / `DateRangeFilter` to
populate the option lists instead of static stubs.
**Out of scope.** `POST /search` filter wiring (Task #52, done),
mounting `FilterPanel` on `/search` (Task #54), `Article.topics`
extractor (P1), `OVER (PARTITION BY ...)`-style cross-facet
correlograms, multi-tenant admin views.

## Semantics decisions (the five calls)

| Decision | Pick | Rationale |
|---|---|---|
| Isolation | **Per-`user_id`** | Multi-tenant: user A's facets must never include user B's articles. Predicate `Article.user_id == current_user.id` is mandatory, non-optional. |
| Source facet key | **`source_domain`** (the column), exposed as `value` in `FacetCount` | `SourceFilter` URL contract is `?source=<domain>`; the option list and the search filter use the same string. |
| Topic facet key | **`Article.topics` element** (each unique topic across the user's articles) | `TopicMultiSelect` URL contract is `?topic=a&topic=b`; one entry per unique topic string. |
| Date range source | **`Article.indexed_at`** (not `publish_date`) | Mirrors Task #52's filter source; `publish_date` is often null on scraped items. |
| Sort order | **`count DESC`, tie-break `value ASC`** | Deterministic; biggest first; stable for snapshot testing. |
| Empty library | **`counts: []`, `date_range: {min: null, max: null}`** (HTTP 200) | Empty state is not an error. Frontend renders an empty dropdown. |

## Edge cases (locked in)

- **Cache key.** `facets:user:{user_id}` (Redis). 60s TTL. No cache key for anonymous — endpoint is authenticated; anonymous request → 401 from the auth dependency, never reaches the handler.
- **Cache stampede.** On a miss the handler recomputes and `SETEX`s the result. Concurrent misses will each run a query; this is acceptable for the 60s-TTL window (rate-limited by per-user traffic, not server-wide). No request coalescing in this task.
- **Topics cardinality.** No cap. Returned list is unbounded; if a user accumulates 10k unique topics the response grows accordingly. Documented limitation; revisit if/when the extractor lands and produces wide topic vocab.
- **Topic dedupe.** `Article.topics` is `text[]`; two articles with `["ai"]` and `["ai","llm"]` contribute one `FacetCount{value: "ai", count: 2}` (one article *with* ai). The count is the number of articles that have the topic, not the number of occurrences.
- **Sources with very long URLs.** Source facet key is `source_domain` (e.g. `reuters.com`) — bounded length. The `value` field on `FacetCount` is the domain, not the full URL. No 200-char concern at the API layer.
- **Source dedupe.** `Article.source_domain` is a single text column; the aggregation is a plain `GROUP BY source_domain`. No dedupe work needed.
- **Topics are case-sensitive.** `"AI"` and `"ai"` are distinct facets. Same convention as Task #52's `SearchFilters.topics` OR-match. (Reconcile with the future extractor's case policy in a follow-up ADR if needed.)
- **Date `min == max`.** Single-article library returns `date_range: {min: <iso>, max: <iso>}` with both bounds equal. Not `{min: null, max: null}`.
- **`Cache-Control` semantics.** `private, max-age=60` — the response is per-user and must not be cached by shared proxies. Same value emitted on both cache hit and miss paths.
- **No `Vary` header required.** Response varies only by `user_id` (which is in the cache key, not the request), so a shared cache could safely share rows — but we tell it not to with `private`.

## Response shape (locked in)

```jsonc
// HTTP 200, Cache-Control: private, max-age=60
{
  "sources": [
    { "value": "reuters.com",  "count": 12 },
    { "value": "nytimes.com",  "count":  7 }
  ],
  "topics": [
    { "value": "ai",   "count": 14 },
    { "value": "llm",  "count":  9 }
  ],
  "date_range": {
    "min": "2026-07-01T10:00:00+00:00",
    "max": "2026-07-08T22:15:31+00:00"
  }
}
```

- `sources` / `topics`: sorted `count DESC, value ASC`. Each item has exactly `{value: string, count: number}`. No `selected` count, no `url`, no `last_seen` — the Frontend does not consume them today (see Open questions).
- `date_range.min` / `date_range.max`: ISO 8601 strings with offset, **or** `null` when the library is empty. Format must be the same one Pydantic's `datetime` serializer emits elsewhere in the API (e.g. `2026-07-08T22:15:31+00:00`).
- 401 (unauthenticated) and 500 (DB error) are the only non-200 paths. No 422 — there are no request body fields.

## Acceptance criteria

### 1. Empty library → all-zero counts, null bounds

- **Given** an authenticated user with zero `Article` rows,
- **When** they `GET /search/facets`,
- **Then** the response is **HTTP 200** with
  `{"sources": [], "topics": [], "date_range": {"min": null, "max": null}}`
  and the `Cache-Control: private, max-age=60` header.

### 2. Single-article library → single-source, single-topic, min == max

- **Given** an authenticated user with exactly one article: `source_domain="reuters.com"`, `topics=["ai"]`, `indexed_at=2026-07-08T10:00:00+00:00`,
- **When** they `GET /search/facets`,
- **Then** the response is HTTP 200 with
  `sources=[{value:"reuters.com", count:1}]`,
  `topics=[{value:"ai", count:1}]`,
  `date_range={min:"2026-07-08T10:00:00+00:00", max:"2026-07-08T10:00:00+00:00"}`.

### 3. Multi-tenant isolation — user A's facets exclude user B's articles

- **Given** user A with 3 articles (sources: `reuters.com`, `nytimes.com`; topics: `["ai"]` × 2, `["crypto"]` × 1) and user B with 1 article (source: `theverge.com`, topic: `["crypto"]`),
- **When** user A `GET`s `/search/facets`,
- **Then** `sources` does not contain `theverge.com`; `topics["crypto"].count == 1` (not 2); `date_range` reflects only user A's articles.

### 4. Topic dedupe — `count` is number of articles, not occurrences

- **Given** user U with 3 articles: A1 `topics=["ai"]`, A2 `topics=["ai","llm"]`, A3 `topics=["ai","llm","rag"]`,
- **When** they `GET /search/facets`,
- **Then** `topics` includes `{value:"ai", count:3}` and `{value:"llm", count:2}` and `{value:"rag", count:1}` — every article with `["ai"]` contributes 1 to `ai`, regardless of how many other topics it also has.

### 5. Sort order — `count DESC, value ASC`

- **Given** user U with: 4 articles on `nytimes.com`, 7 on `reuters.com`, 2 on `theverge.com`,
- **When** they `GET /search/facets`,
- **Then** `sources` is `[{reuters.com, 7}, {nytimes.com, 4}, {theverge.com, 2}]` in that order. No SQL `ORDER BY` randomness leaking into the response.

### 6. Cache hit path — second call within 60s is identical

- **Given** user U with N articles,
- **When** they call `GET /search/facets` twice within 60s,
- **Then** the second response is **byte-equal** to the first (the same JSON body, same header `Cache-Control: private, max-age=60`).
- **And** the underlying aggregation query is **not** executed twice — verified by spying on the SQLAlchemy session in the test (e.g. `engine.connect()` event count).

### 7. Cache miss path — after 60s the third call recomputes

- **Given** user U with N articles,
- **When** they call `GET /search/facets`, then advance the test clock by ≥ 60s, then call again,
- **Then** the second call **re-runs** the aggregation (verified via the same spy as criterion 6) and the cache is repopulated.
- **Implementation hint:** the Backend should use `freezegun` or a `monkeypatch` on `time.time` / `datetime.utcnow` in the Redis `SETEX` path.

### 8. `Cache-Control: private, max-age=60` always emitted

- **Given** any authenticated user (library empty or not),
- **When** they call `GET /search/facets`,
- **Then** the response carries `Cache-Control: private, max-age=60` on both the cache-hit and cache-miss paths. (No `public`, no `s-maxage`, no `no-store`.)

### 9. Unauthenticated request — 401

- **Given** an anonymous client (no / expired JWT cookie),
- **When** they call `GET /search/facets`,
- **Then** the response is **HTTP 401** and the handler does not run (the auth dependency short-circuits).

### 10. `date_range` ISO 8601 format

- **Given** user U with at least one article,
- **When** they `GET /search/facets`,
- **Then** `date_range.min` and `date_range.max` parse with `datetime.fromisoformat()` without raising. (Round-trip-safe; lets the Frontend feed them into `new Date()` without a custom parser.)

## Edge case matrix

| # | Scenario | Expected |
|---|---|---|
| E1 | Library empty | `sources=[], topics=[], date_range={null, null}`, 200 |
| E2 | Library with one article, no topics (`topics=[]`) | `topics=[]`, `sources=[{value, count:1}]`, `date_range.min == max == indexed_at` |
| E3 | Article with `source_domain` of 200+ chars (malformed) | `value` is the full string, count is 1. No truncation. Documented limitation. |
| E4 | 10k-article library, 50 unique sources, 500 unique topics | HTTP 200 in <200 ms p95 on the staging hardware budget; response body ≤ 200 KB |
| E5 | All articles have `topics=[]` | `topics=[]` (not `null`, not omitted). Same shape as the empty-topics case. |
| E6 | Two articles, same source, same indexed_at second | `sources[0].count == 2`; `date_range.min == max` |
| E7 | One article, `indexed_at` set, `publish_date=null` | `date_range` is computed from `indexed_at` (the only non-null timestamp). Documented decision: indexed_at, not publish_date. |
| E8 | User with one article then deletes it, then calls `/search/facets` | Cached response may still include the deleted article for up to 60 s. **Accepted trade-off** — bounded staleness within the TTL window; the web client re-queries on user interaction (dropdown open / keystroke / page focus), so staleness is not user-visible. See ADR-020 §Consequences "Bounded staleness" (Task #53 Devil-follow-up, 2026-07-08). |

## Open questions for the PM

These are gaps between the **current** Frontend contracts and the **spec'd** Backend response. They are not blocking — the Backend can ship as spec'd and Task #54 (mounting) can adapt — but the PM should confirm before Task #54 starts.

1. **`FilterPanel.sources: string[]` vs `FacetsResponse.sources: FacetCount[]`.** The current `FilterPanel` prop shape (`apps/web/src/components/filters/FilterPanel.tsx:25`) is `sources: string[]`. The spec'd `FacetsResponse.sources[i]` is `{value, count}`. Task #54 will either (a) reshape the prop to `FacetCount[]` and teach `SourceFilter` to render `count` next to each option, or (b) the Backend also returns a flat `sources: string[]` for backward compat. **Pick one.** Option (a) is the better long-term API; the spec currently implies it but the Backend contract doesn't promise it as a top-level convenience field.

2. **`FilterPanel.topics: MultiSelectOption[]` and `MultiSelectOption = {value, label}`.** Same shape mismatch as #1, plus the `label` field — the current prop has `label` (for display) and `value` (for URL). The spec'd `FacetCount` is `{value, count}` only. If the topic label should differ from the topic value (e.g. a future LLM-generated canonical label), that needs to be either baked into the Backend response or mapped in a Frontend selector. **Recommend:** treat the value as its own label for now (matches today's `TopicMultiSelect` behavior — it passes `value` to `MultiSelect`, which uses it as both).

3. **No `selected` count / no total.** The Frontend cannot show a "(N) selected" badge or a "12 of 7,431 articles" footer from the spec'd payload. If the PM wants those, the Backend needs to grow `FacetCount` with `selected?: number` and `FacetsResponse` with `total_articles?: number`. **Recommend:** defer to a future task; out of scope for #53.

4. **No facet pagination / `limit` cap.** A user with 50k unique topics would get a 5 MB JSON. **Recommend:** cap `topics` at e.g. 200 entries and add a `topics_truncated: boolean` flag, OR open question for the PM: "do we expect <1k unique topics per user in practice?". Today's extractor (per `TopicMultiSelect.tsx:11`) doesn't even populate `topics` — the value is 0 — so this is theoretical for MVP. **Recommend:** no cap in #53, revisit when the extractor lands.

5. **No `Cache-Control: must-revalidate`.** Some CDNs treat `private, max-age=60` as "use stale for 60s, then revalidate in the background". For per-user data, `private` is sufficient. **Confirm:** the spec's `private, max-age=60` is intentional, not a copy-paste from a public-cacheable endpoint.

## Test coverage map — `apps/api/tests/test_search_facets.py`

Tests use the `test_TN_*` convention (`T1..T6`, `T1b`, `T7`, `T8`, `T9`)
so the AC criterion number is preserved in the function name. The
table below maps each criterion to its concrete test function as of
the Task #53 follow-ups (M-2 added `test_T9`).

| Criterion | Test name | What it asserts |
|---|---|---|
| 1 empty | `test_T1_empty_library_returns_zero_counts` | 200, empty arrays, null bounds, `Cache-Control` header present. |
| 2 single-article | `test_T2_single_article_populates_one_bucket_per_dimension` | count=1 across the board, `min == max`. |
| 3 isolation | `test_T5_two_users_with_disjoint_libraries_see_disjoint_facets` | User A's response excludes user B's rows; uses two `client` sessions with different JWTs. |
| 4 topic dedupe | `test_T1b_duplicate_topic_in_single_article_counts_as_one` | A single article with `topics=['ai','ai']` counts as one, not two (Devil C1). |
| 5 sort | `test_T3_mixed_library_sorted_desc_by_count_with_brackets` | 3-source fixture; order matches `count DESC, value ASC`. |
| 6 cache hit | `test_T4_cache_miss_then_hit_within_ttl` | Two calls within 60s; second is `X-Cache: HIT`; `set_calls` does not increment. |
| 7 cache miss | `test_T7_cache_miss_after_ttl_recomputes` | First call writes with `ex=0` (TTL collapsed); second call recomputes and is also MISS (Devil H3). |
| 8 header | `test_T4_cache_miss_then_hit_within_ttl` (combined with #6) | `Cache-Control: private, max-age=60` is asserted on the first call of T4; same value emitted on both paths. |
| 9 auth | `test_T8_unauthenticated_returns_401` | No override → 401; facets keys absent from body. |
| 10 ISO format | `test_T2_single_article_populates_one_bucket_per_dimension` | `datetime.fromisoformat` parses the `min`/`max` strings (asserted via the explicit `==` check on the `2026-07-01T12:00:00Z` ISO value). |
| M-2 partial-failure | `test_T9_per_dim_exception_returns_200_with_degraded_dimensions` | `_aggregate_topics` monkeypatched to raise → 200, sources/date_range populated, `topics=[]`, `degraded_dimensions=["topics"]`. |

Additional safety tests:
- `test_T6_cache_keys_are_user_scoped` — `facets:` prefix plus distinct UUID suffix across three users; regression guard against a global cache key.
- `test_T9_per_dim_exception_returns_200_with_degraded_dimensions` — Devil M-2; partial-failure shape is stable JSON, not a 500.

## Implementation hints for Backend Dev (non-binding)

- One SQL aggregation per dimension, three total. `Article` has the columns; do not call Chroma.
  - Sources: `SELECT source_domain AS value, COUNT(*) AS count FROM articles WHERE user_id = :uid GROUP BY source_domain ORDER BY count DESC, value ASC`
  - Topics: `SELECT topic, COUNT(*) AS count FROM articles, unnest(topics) AS topic WHERE user_id = :uid GROUP BY topic ORDER BY count DESC, topic ASC`
  - Date range: `SELECT MIN(indexed_at), MAX(indexed_at) FROM articles WHERE user_id = :uid` (returns `(None, None)` on empty).
- Redis: `GET facets:user:{user_id}` → on miss, compute, `SETEX facets:user:{user_id} 60 <json>`.
- New Pydantic schemas in `apps/api/api/schemas/search.py`:
  - `class FacetCount(BaseModel): value: str; count: int`
  - `class FacetDateRange(BaseModel): min: datetime | None; max: datetime | None`
  - `class FacetsResponse(BaseModel): sources: list[FacetCount]; topics: list[FacetCount]; date_range: FacetDateRange`
- `Cache-Control: private, max-age=60` set on the FastAPI `Response` object inside the handler, NOT via a global middleware (so it doesn't leak to other endpoints that should not be cached).
- Mirrored TS types live in `packages/shared/src/types.ts` once the schemas land; see the existing `SearchFilters` mirror for the pattern.
