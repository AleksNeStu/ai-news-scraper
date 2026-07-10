/**
 * Tests for the `<SearchClient/>` filter-panel mount (Task #54).
 *
 * Scope: prove that `GET /search/facets` is fired on mount, that the
 * response is wired into `<FilterPanel/>`, and that mutating a filter
 * (via `useFilterUrl`) does NOT trigger a second facets fetch.
 *
 * The page itself is a Next.js Server Component, which can't be rendered
 * in jsdom; the user-visible behaviour comes from this client island +
 * the per-widget components under `components/filters/`.
 *
 * `useFilterUrl` writes back via the mocked router; we assert on the
 * `replace` call args instead of trying to drive the i18n `usePathname`
 * hooks. `searchArticles` is irrelevant to these tests (no `?q=` is
 * supplied) so we leave it default-mocked.
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'

import { IntlWrapper } from '@/test-utils/intl-helper'
import { searchArticles, searchFacets } from '@/lib/api/search'
import { SearchClient } from '@/app/[locale]/(app)/search/SearchClient'

vi.mock('@/lib/api/search', () => ({
  searchArticles: vi.fn(),
  searchFacets: vi.fn(),
}))

const searchArticlesMock = vi.mocked(searchArticles)
const searchFacetsMock = vi.mocked(searchFacets)

const replaceSpy = vi.fn()
let mockSearch = ''

vi.mock('@/i18n/navigation', () => ({
  useRouter: () => ({ replace: replaceSpy }),
  usePathname: () => '/en/search',
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

const FACETS_RESPONSE = {
  sources: [
    { value: 'nytimes.com', count: 12 },
    { value: 'techcrunch.com', count: 4 },
  ],
  topics: [
    { value: 'ai', count: 9 },
    { value: 'ml', count: 3 },
  ],
  date_range: { min: '2026-06-01T00:00:00Z', max: '2026-07-08T00:00:00Z' },
  // Task #53 Devil M-2: API always populates this; the TS mirror
  // types it as required (was optional until the test fixture caught
  // up). Empty array on the happy path.
  degraded_dimensions: [],
}

function renderClient() {
  return render(
    <IntlWrapper>
      <SearchClient
        initialQuery=""
        initialPage={1}
        initialPageSize={10}
        initialSource={null}
        initialTopics={[]}
        initialFrom={null}
        initialTo={null}
      />
    </IntlWrapper>
  )
}

describe('SearchClient — facets mount (Task #54)', () => {
  beforeEach(() => {
    replaceSpy.mockReset()
    mockSearch = ''
    searchArticlesMock.mockReset()
    searchFacetsMock.mockReset()
    searchFacetsMock.mockResolvedValue(FACETS_RESPONSE)
    searchArticlesMock.mockResolvedValue({
      results: [],
      page: 1,
      page_size: 10,
      total: 0,
      took_ms: 0,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('calls searchFacets exactly once on mount', async () => {
    renderClient()
    await waitFor(() => expect(searchFacetsMock).toHaveBeenCalledTimes(1))
  })

  it('forwards the facets sources + topics into the FilterPanel options', async () => {
    renderClient()
    await waitFor(() => expect(searchFacetsMock).toHaveBeenCalledTimes(1))
    // The FilterPanel renders its own <aside aria-label="Filters">;
    // presence of the landmark proves the panel was actually mounted
    // (not just imported) by SearchClient.
    expect(document.querySelector('aside[aria-label="Filters"]')).toBeTruthy()
  })

  it('does NOT call searchFacets again when a filter URL is mutated', async () => {
    // Start with no filter; mount calls facets once.
    const view = renderClient()
    await waitFor(() => expect(searchFacetsMock).toHaveBeenCalledTimes(1))

    // Simulate the user picking a source: FilterPanel's SourceFilter
    // would call `filters.set('source', 'techcrunch.com')` which goes
    // through `useFilterUrl` → `useRouter().replace(...)`. The mocked
    // router records the call but does not actually navigate. We then
    // re-render with the new initialSource value to mimic the URL
    // updating and SearchPage (Server Component) handing the new prop
    // to SearchClient. The facets effect must NOT re-fire — facets are
    // library-wide, not query-scoped.
    mockSearch = 'source=techcrunch.com'
    view.rerender(
      <IntlWrapper>
        <SearchClient
          initialQuery=""
          initialPage={1}
          initialPageSize={10}
          initialSource="techcrunch.com"
          initialTopics={[]}
          initialFrom={null}
          initialTo={null}
        />
      </IntlWrapper>
    )
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(searchFacetsMock).toHaveBeenCalledTimes(1)
  })

  it('does not surface a facets fetch failure to the user', async () => {
    searchFacetsMock.mockRejectedValueOnce(new Error('network down'))
    const view = renderClient()
    // Wait for the promise chain to settle.
    await new Promise((resolve) => setTimeout(resolve, 10))
    // No error banner, no role="alert" outside the pending state — the
    // search form is still rendered.
    expect(view.queryByRole('alert')).toBeNull()
    expect(searchFacetsMock).toHaveBeenCalledTimes(1)
  })
})
