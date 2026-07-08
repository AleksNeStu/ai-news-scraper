# Task #52 — Acceptance Criteria: SearchFilters.topics + date_from + date_to

**Scope.** Wire `SearchFilters.topics`, `date_from`, `date_to` server-side on `POST /search`. Source filter already works; keep it green.
**Out of scope.** Facets endpoint (#53), mounting `FilterPanel` on `/search` (#54), `Article.topics` extractor.

## Semantics decisions (the four calls)

| Decision | Pick | Rationale |
|---|---|---|
| Topics multi-match | **OR** (any of N) | Matches user mental model: "show me articles about **AI** OR **LLM**". AND would over-narrow to nothing for casual browsing. |
| `date_from` lower bound | **Inclusive** | Inclusive lower bound feels natural for a date picker ("from Jul 1"). |
| `date_to` upper bound | **Inclusive (end-of-day)** | User picks a calendar day, not an instant. Bound is `date_to + 23:59:59.999999 UTC`. |
| `date_to < date_from` | **422 (Pydantic)** | Cleanest failure mode; client can render an inline form error. Alternative (silent swap) hides bugs. |

## Edge cases (locked in)

- **Timezone.** Both bounds parsed as UTC midnight (`date_from`) / end-of-day UTC (`date_to`). Local-tz support is a future ADR; do not parse a tz offset in this task.
- **Empty `topics=[]`.** Treated as "no topic filter". Same as omitting the field.
- **`topics` length.** No cap in this task. Documented limitation; revisit if a user pastes 1000 topics.
- **Zero-match result.** `total=0, results=[], took_ms>0` — same shape as embedder miss.
- **Filter drops more than over-fetch cap.** `total` reports the post-slice count (`<= over_fetch`). For very deep pages, `total` may under-report. Documented limitation; full-fidelity `total` needs a separate `count(...)` query (out of scope for #52, in-scope for #53 facets).

## Acceptance criteria

### 1. `source` filter — regression

- **Given** an authenticated user with articles from `reuters.com` and `nytimes.com`,
- **When** they POST `/search` with `filters={"source": "reuters.com"}`,
- **Then** the Chroma `where` clause contains `{"user_id": ..., "source_domain": "reuters.com"}` and every result has `article.source_domain == "reuters.com"`.

### 2. `topics` filter — any-of-N semantics

- **Given** three articles A1 (topics: `["ai","llm"]`), A2 (topics: `["ai"]`), A3 (topics: `["crypto"]`),
- **When** the user posts `filters={"topics": ["ai", "llm"]}`,
- **Then** A1 and A2 are returned; A3 is not. Topics are matched **OR**: a row is kept if any of its topics overlaps the query list.
- **And** when `topics=[]` or `topics=null`, no topic predicate is applied (treated as no filter).

### 3. `date_from` filter — inclusive lower bound

- **Given** an article with `indexed_at = 2026-07-08T10:00:00Z`,
- **When** the user posts `filters={"date_from": "2026-07-08"}`,
- **Then** the article is included (boundary is inclusive). Parsed as `2026-07-08T00:00:00Z`.
- **And** `date_from = 2026-07-09` excludes that same article.

### 4. `date_to` filter — inclusive end-of-day

- **Given** the same article (`indexed_at = 2026-07-08T10:00:00Z`),
- **When** the user posts `filters={"date_to": "2026-07-08"}`,
- **Then** the article is included (the bound is `2026-07-08T23:59:59.999999Z`, end-of-day UTC).
- **And** `date_to = 2026-07-07` excludes that same article.

### 5. Combined filters — intersection

- **Given** A1 (source=`reuters`, topics=`["ai"]`, indexed=Jul 8), A2 (source=`reuters`, topics=`["crypto"]`, indexed=Jul 8), A3 (source=`nytimes`, topics=`["ai"]`, indexed=Jul 8),
- **When** the user posts `filters={"source": "reuters", "topics": ["ai"], "date_from": "2026-07-08", "date_to": "2026-07-08"}`,
- **Then** only A1 is returned. Filters AND together; topics still OR within their field.

### 6. Empty / omitted filters

- **Given** any corpus,
- **When** the user posts `filters=None` or `filters={}` (no fields set),
- **Then** behaviour is identical to today: only `user_id` is in the `where` clause; no source/topic/date predicate is added.

### 7. Invalid `date_to < date_from` — 422

- **Given** a payload with `filters={"date_from": "2026-07-08", "date_to": "2026-07-07"}`,
- **When** the request is sent,
- **Then** FastAPI returns **422** with `detail[*].loc == ["body", "filters"]` and `type` indicating a model validator failure (`value_error`).
- **And** no Chroma / DB query runs (Pydantic validation rejects before the handler).

### 8. Pagination interaction with filtered `total`

- **Given** 25 hits when filtered, `page_size=10`,
- **When** the user requests `page=1`, `page=2`, `page=3`,
- **Then** `total == 25` on every page; pages 1 and 2 return 10 results, page 3 returns 5. `total` reflects the **filtered** candidate count, not the unfiltered one.

## Test coverage map — `apps/api/tests/test_search_filters.py`

| Criterion | Test name | What it asserts |
|---|---|---|
| 1 source regression | `test_source_filter` | Only matching `source_domain` rows survive; existing behaviour preserved. |
| 2 topics OR | `test_topics_filter_or_semantics` | `["ai","llm"]` keeps A1 (both) + A2 (ai only); drops A3 (crypto only). |
| 2 topics empty | `test_empty_topics_is_no_filter` | `topics=[]` matches the no-filter baseline. |
| 3 date_from inclusive | `test_date_from_inclusive` | Boundary article at `00:00:00Z` is kept; `date_from + 1 day` drops it. |
| 4 date_to end-of-day | `test_date_to_end_of_day_inclusive` | Article at `10:00:00Z` kept when `date_to = same day`; dropped when `date_to = day - 1`. |
| 5 combined | `test_combined_filters_intersect` | Source + topics + date all set; only the row matching every dimension survives. |
| 6 empty filters | `test_empty_filters_match_baseline` | `filters=None` and `filters={}` byte-equal the no-filter response shape. |
| 7 invalid range | `test_invalid_date_range_returns_422` | `date_to < date_from` → 422, no vector call. |
| 8 pagination + filters | `test_pagination_total_reflects_filtered_count` | 25 filtered hits across 3 pages of size 10; `total=25` every page; correct slice sizes. |

Additional safety test: `test_filter_drops_all_candidates_returns_empty_with_zero_total` — `total=0, results=[]` when predicate eliminates everything.

## Implementation hints for Backend Dev (non-binding)

- `SearchFilters` gains a `model_validator` for `date_to >= date_from` (raises `ValueError` → 422).
- `search.py:50-52` builds the Chroma `where` clause incrementally:
  - `user_id` always (unchanged).
  - `source_domain` if `filters.source`.
  - Date bounds on `indexed_at` (`{"$gte": date_from_iso}` / `{"$lte": date_to_eod_iso}`) if set.
  - Topics use Chroma's `$contains`-equivalent on `topics` — operator depends on the Chroma adapter; mirror the existing `where` pattern.
- `total` is the **post-filter slice length** (existing `len(full_results)`), NOT a separate count. Over-fetch remains `page * page_size`. See edge case bullet above for the very-deep-pages caveat.
- Hydrate step in `search.py:74-77` is filter-agnostic; no change needed there unless a filter drops the article entirely (in which case it never appears in `raw` from Chroma).
