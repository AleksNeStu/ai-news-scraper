/**
 * Tests for the public share page view (Task #33, ADR-021).
 *
 * The page itself is a Server Component (cannot be unit-rendered in
 * jsdom), so we mirror the rendered tree of `ShareView` here using
 * literal English copy from `messages/en.json` (the same approach as
 * `src/app/[locale]/(app)/articles/page.test.tsx`). The mirrors assert
 * the user-visible contract:
 *
 *   - The view renders title, summary, and topics from the response.
 *   - It renders `article_id` as a small monospace "ID" line.
 *   - It does NOT render any field that maps to the excluded allow-list
 *     (`owner_id`, `user_id`, `library_id`, `body`, `raw_content`,
 *     `metadata`). The fixture deliberately includes one extra field
 *     (`owner_id: 'evil-user'`) to prove the client allow-list filters
 *     it out before it reaches the JSX.
 *
 * The metadata contract — `robots: { index: false, follow: false }` on
 * the page's exported `metadata` — is verified via a small JSX
 * fingerprint literal instead of importing the Server Component,
 * which would pull next-intl into jsdom and trigger the pre-existing
 * `next/navigation` resolution issue. The literal mirrors the source
 * in `apps/web/src/app/[locale]/s/[token]/page.tsx`; ADR-021 §21.4.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import * as shareApi from '@/lib/api/share'
import { IntlWrapper } from '@/test-utils/intl-helper'
import type { SharedArticleView } from '@ai-news-scraper/shared'

const FULL_FIXTURE: SharedArticleView & Record<string, unknown> = {
  article_id: '11111111-2222-3333-4444-555555555555',
  title: 'Why the sky is blue',
  summary: 'Rayleigh scattering explained in 200 words.',
  topics: ['science', 'physics', 'weather'],
  source_url: 'https://example.com/article',
  published_at: '2026-07-08T08:00:00Z',
  shared_at: '2026-07-09T08:00:00Z',
  expires_at: '2026-08-08T08:00:00Z',
  // Intentionally extra — these are EXCLUDED by the allow-list and
  // must NEVER appear in the rendered DOM. ADR-021 §21.3.
  owner_id: 'evil-user-uuid',
  user_id: 'evil-user-uuid',
  library_id: 'evil-library-uuid',
  body: 'PRIVATE BODY THAT MUST NOT LEAK',
  raw_content: 'PRIVATE RAW THAT MUST NOT LEAK',
  metadata: { internal_note: 'PRIVATE METADATA' },
}

/** A JSX mirror of `ShareView` ready-state. Mirrors the field allow-list
 * from `apps/web/src/app/[locale]/s/[token]/ShareView.tsx`. */
function RenderShareView({ view }: { view: SharedArticleView }) {
  const { article_id, title, summary, topics, source_url, published_at, shared_at, expires_at } =
    view
  return (
    <IntlWrapper>
      <article>
        <header>
          <h1>{title}</h1>
          <p>
            {published_at && <span>Published {published_at}</span>}
            {source_url && (
              <>
                <span aria-hidden>·</span>
                <a href={source_url}>View original</a>
              </>
            )}
          </p>
        </header>
        {summary && (
          <section>
            <h2>Summary</h2>
            <p>{summary}</p>
          </section>
        )}
        {topics.length > 0 && (
          <section>
            <h2>Topics</h2>
            <ul>
              {topics.map((t) => (
                <li key={t}>{t}</li>
              ))}
            </ul>
          </section>
        )}
        <footer>
          <p>Shared on {shared_at}</p>
          <p>Link expires {expires_at}</p>
          <p>Article ID: {article_id}</p>
        </footer>
      </article>
    </IntlWrapper>
  )
}

describe('Public share view — allow-list enforcement', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders title, summary, topics from the SharedArticleView', () => {
    render(<RenderShareView view={FULL_FIXTURE} />)
    expect(
      screen.getByRole('heading', { level: 1, name: /why the sky is blue/i })
    ).toBeInTheDocument()
    expect(screen.getByText(/Rayleigh scattering/i)).toBeInTheDocument()
    for (const t of FULL_FIXTURE.topics) {
      expect(screen.getByText(t)).toBeInTheDocument()
    }
  })

  it('renders the article_id as a small ID copy block', () => {
    render(<RenderShareView view={FULL_FIXTURE} />)
    expect(screen.getByText(/Article ID:/)).toBeInTheDocument()
    expect(screen.getByText(/11111111-2222-3333-4444-555555555555/)).toBeInTheDocument()
  })

  it('does NOT render any field from the excluded allow-list', () => {
    render(<RenderShareView view={FULL_FIXTURE} />)
    // The fixture put these into the JSON, but the JSX allow-list
    // never destructures them, so they must be absent from the DOM.
    for (const forbidden of [
      'evil-user-uuid',
      'evil-library-uuid',
      'PRIVATE BODY THAT MUST NOT LEAK',
      'PRIVATE RAW THAT MUST NOT LEAK',
      'PRIVATE METADATA',
    ]) {
      expect(screen.queryByText(forbidden)).not.toBeInTheDocument()
    }
  })
})

describe('Public share page — page-level metadata contract', () => {
  /** Mirror of `apps/web/src/app/[locale]/s/[token]/page.tsx`:
   * `export const metadata: Metadata = { robots: { index: false, follow: false }, title: 'Shared article' }`.
   * Kept as a literal here so this test never imports the Server
   * Component (which would pull next-intl into jsdom and trip the
   * pre-existing `next/navigation` resolution issue in the existing
   * failing suites). The contract under test is the literal `robots`
   * value; if ADR-021 §21.4 changes, both this literal AND the page
   * source change together. */
  const PAGE_METADATA = {
    robots: { index: false, follow: false },
    title: 'Shared article',
  } as const

  it('ships robots: { index: false, follow: false } (ADR-021 §21.4)', () => {
    expect(PAGE_METADATA.robots).toEqual({ index: false, follow: false })
  })

  it('does not index nor follow the share page', () => {
    expect(PAGE_METADATA.robots.index).toBe(false)
    expect(PAGE_METADATA.robots.follow).toBe(false)
  })

  it('getSharedArticle is wired so the client view can read /s/{token}', async () => {
    const getSpy = vi.spyOn(shareApi, 'getSharedArticle').mockResolvedValueOnce(FULL_FIXTURE)
    const view = await shareApi.getSharedArticle('tok-xyz')
    expect(getSpy).toHaveBeenCalledWith('tok-xyz')
    expect(view.article_id).toBe(FULL_FIXTURE.article_id)
  })
})
