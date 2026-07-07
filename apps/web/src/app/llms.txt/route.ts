/**
 * /llms.txt — canonical AI-agent discovery surface (Task #28 Frontend half).
 *
 * Follows the 4-rule format published by Answer.AI and adopted across
 * ChatGPT, Claude, Perplexity, and Google-Extended crawlers. The shape
 * is rendered by the Architect's `buildLlmsTxt` builder; this file is
 * the thin Next.js Route Handler wrapper.
 *
 * Pattern reference: `apps/web/src/app/sitemap.ts` — same `SITE_URL` +
 * `getPathname` + `routing.locales` plumbing.
 *
 * Caching:
 *   - `revalidate = 3600` (1 hour) matches the Allowlist sections of
 *     LLMS_LOCALES and the public-route surface in `sitemap.ts`. The
 *     route also ships a `Cache-Control: public, max-age=3600` header
 *     so CDNs and crawlers can cache it client-side.
 *
 * Locale coverage:
 *   - The Architect's `LLMS_LOCALES = ['en', 'ru']` is the single
 *     source of truth inside the builder. When `routing.locales` adds
 *     a third locale, update BOTH `LLMS_LOCALES` (in the shared
 *     package) and `routing.locales` (here) in tandem — the route
 *     handler delegates the locale list to the builder.
 */

import { buildLlmsTxt, type LlmsPathResolver } from '@ai-news-scraper/shared'
import { getPathname } from '@/i18n/navigation'
import { SITE_URL } from '@/lib/site'
import { SITE_DESCRIPTION } from '@/lib/structured-data/builders'

export const revalidate = 3600

export function GET() {
  const resolvePath: LlmsPathResolver = ({ locale, path }) => getPathname({ locale, href: path })

  const body = buildLlmsTxt(
    {
      name: 'ai-news-scraper',
      summary: SITE_DESCRIPTION,
      // Empty sections — the builder emits the canonical allowlist
      // automatically, expanded per locale.
      sections: [],
    },
    { siteUrl: SITE_URL, resolvePath }
  )

  return new Response(body, {
    headers: {
      'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'public, max-age=3600, s-maxage=3600',
    },
  })
}
