# Task #54 Fetcher Contract — Hand-off (2026-07-09)

## Scope

Task #54 mounts the existing `<FilterPanel/>` component into `/search` so the
URL-bound filter widgets (Source, Topics, Date) render alongside the search
results. The panel is currently orphan (`apps/web/src/components/filters/FilterPanel.tsx`)
and needs a fetcher for the option lists served by `GET /search/facets` (shipped
in commit `8bb183d`, ADR-020). This hand-off defines the TS signature, the
URL-state contract, and the mount point for the Frontend teammate. No business
logic or production code is changed by this Architect step.

## TS signature

Add to `apps/web/src/lib/api/search.ts` (next to `searchArticles`):

```ts
import type { FacetsResponse } from '@ai-news-scraper/shared'

/**
 * Fetch per-dimension facet aggregations for the current user's library.
 *
 * Hits `GET /search/facets`. No request body. `signal` is forwarded so
 * React Query / the FilterPanel mount can cancel an in-flight request on
 * unmount or when the user-id changes.
 *
 * Server side is Redis-cached (60s TTL, keyed on `facets:{user_id}`);
 * the response also ships `Cache-Control: private, max-age=60`. To match
 * server freshness at the React Query layer, configure
 * `staleTime: 60_000` on the consuming `useQuery`.
 *
 * Empty library returns `{ sources: [], topics: [], date_range: { min: null, max: null } }`
 * with HTTP 200 — this is NOT an error. UI should render the "empty library"
 * placeholder when both date bounds are null.
 *
 * Throws `ApiError` (from `@/lib/api`) on non-2xx.
 */
export async function searchFacets(
  init?: RequestInit & { signal?: AbortSignal }
): Promise<FacetsResponse> {
  return api.get<FacetsResponse>('/search/facets', init)
}
```

Notes:

- `FacetsResponse`, `FacetCount`, and `FacetDateRange` are already exported
  from `@ai-news-scraper/shared` (see `packages/shared/src/types.ts` lines
  93-128) — do NOT re-declare locally.
- `api.get` already forwards `init` (including `signal`) and throws `ApiError`
  on non-2xx via the shared `handle` wrapper in `apps/web/src/lib/api.ts`.
- No bespoke error class needed; reuse the existing `ApiError`.

## URL contract

`useFilterUrl()` (in `apps/web/src/components/filters/useFilterUrl.ts`) already
exposes the keys the three filter widgets need. Do NOT re-invent them:

| URL key | Type | Widget | Example |
|---|---|---|---|
| `source` | single string | `SourceFilter` | `?source=nytimes.com` |
| `topic` | repeatable | `TopicMultiSelect` | `?topic=ai&topic=ml` |
| `from` | single ISO date (`YYYY-MM-DD`) | `DateRangeFilter` lower bound | `?from=2026-06-01` |
| `to` | single ISO date (`YYYY-MM-DD`) | `DateRangeFilter` upper bound | `?to=2026-07-08` |

Other keys on the `/search` page (`q`, `page`, `page_size`) are owned by
`SearchClient` and must continue to round-trip through `useFilterUrl` untouched.

The hook auto-resets `page` to `null` on any mutation; the filter widgets
inherit this for free.

## Mount point recommendation

`<aside aria-label="Filters"><FilterPanel/></aside>` rendered **as a sibling
to `<main>` inside `SearchClient.tsx`'s outermost container**, not inside
`<main>`. Concretely: wrap the existing `<main>` and the new `<aside>` in
a flex/grid container so the filters sit to the left and the search column
stays at `max-w-4xl` for readability.

Why this layout:

- `SearchClient.tsx` already owns the URL state — `useFilterUrl()` — so the
  panel and the search form can read the same URL without prop-drilling.
- Rendering the `<aside>` outside `<main>` keeps the filter landmark
  distinct from the search-results landmark, which is what WCAG 1.3.1
  (Info and Relationships) wants when two regions coexist on one page.
- The existing `FilterPanel` component already wraps its children in
  `<aside aria-label={label}>` (see `FilterPanel.tsx:35`), so the
  `aria-label="Filters"` default already satisfies the landmark contract.
  Do not add a second `<aside>` wrapper.

Alternative (NOT chosen): sibling layout in `page.tsx` (Server Component).
Rejected because `page.tsx` is a Server Component and the panel needs
`useFilterUrl()` (a client hook). Hoisting `useFilterUrl` to the server
would require re-architecting the URL contract.

A11y note (Task #27 audit in-progress): the `/search` page is part of the
Task #27 a11y audit (`a11y/ai-news-scraper/audit-report.md`). When mounting:

- Do NOT strip `aria-label`, `role`, or other landmark attributes from
  `FilterPanel`, `SearchClient`, or the form (`role="search"`).
- Do NOT nest the `<aside>` inside the `<form role="search">` — they are
  sibling regions and must stay siblings.
- The `Cache-Control: private, max-age=60` header on `/search/facets`
  does not exempt us from axe-core's "ensure landmarks are unique"
  check; the `aria-label="Filters"` default on `<aside>` is the
  disambiguator and must remain.

## Type mirror status

Confirmed: the TS `FacetsResponse` mirror in
`packages/shared/src/types.ts:118-128` matches the Pydantic
`FacetsResponse` in `apps/api/api/schemas/search.py:128-143` field-for-field:

| TS field | Pydantic field | Type match |
|---|---|---|
| `sources: FacetCount[]` | `sources: list[FacetCount]` | OK |
| `topics: FacetCount[]` | `topics: list[FacetCount]` | OK |
| `date_range: FacetDateRange` | `date_range: FacetDateRange` | OK |
| `FacetCount.value: string` | `value: str` | OK |
| `FacetCount.count: number` | `count: int` | OK |
| `FacetDateRange.min: string \| null` | `min: Optional[datetime] = None` | OK (ISO string vs datetime) |
| `FacetDateRange.max: string \| null` | `max: Optional[datetime] = None` | OK (ISO string vs datetime) |

No drift detected. Both ends use a 60s Redis TTL
(`apps/api/api/services/facet_cache.CACHE_TTL_SECONDS = 60`), no
schema-versioning header. Frontend should treat the TS mirror as the
source of truth for the wire shape and not introduce a parallel type.

## Green light

Frontend may proceed:

1. Add `searchFacets()` to `apps/web/src/lib/api/search.ts` per the
   signature above.
2. In `SearchClient.tsx`, add a `<aside aria-label="Filters"><FilterPanel .../></aside>`
   sibling to the existing `<main>`, wired through `useQuery` (or any
   equivalent) with `staleTime: 60_000`.
3. Pass the response's `sources` and `topics` arrays to `FilterPanel`
   via its existing `sources` and `topics` props. The `date_range` is
   used by `DateRangeFilter` internally via its own props (out of scope
   here; Frontend may extend `DateRangeFilter` to accept `min`/`max`
   from the facets response or read from URL state — the contract
   does not pin this).
4. Do not modify `apps/api/**`, `packages/shared/**`, or any file under
   `tests/`.

No blockers discovered. The `/search/facets` endpoint is live, the
shared types are mirrored, the URL contract is centralized, and the
mount point keeps a11y attributes intact.
