/**
 * Multi-locale sitemap (Task #32).
 *
 * Emits one entry per (route × locale) plus the `alternates.languages`
 * field for every static route so crawlers (and AI agents reading
 * llms.txt / agents.json) can discover every localized variant in a
 * single fetch.
 *
 * Public routes only — the (app) auth-protected sections are listed too
 * because search engines crawl them, the auth gate lives in middleware
 * at render time. Individual article / digest URLs are NOT listed here
 * because they come from user data (Postgres) and would explode the
 * sitemap; search engines discover them through normal crawling.
 *
 * `NEXT_PUBLIC_SITE_URL` is read at request time (App Router supports
 * reading env in `app/sitemap.ts`); we fall back to localhost for dev
 * so the route renders even when the env var is unset.
 */

import type { MetadataRoute } from 'next'
import { getPathname } from '@/i18n/navigation'
import { routing } from '@/i18n/routing'
import { SITE_URL } from '@/lib/site'

// Canonical paths for every public + auth-gated route. Each one emits
// both the bare-en and prefixed-ru variant via getPathname().
const ROUTES = [
  '/',
  '/articles',
  '/dashboard',
  '/dashboard/brief',
  '/feeds',
  '/scrape',
  '/search',
  '/settings',
  '/login',
  '/register',
  '/unsubscribe',
] as const

export default function sitemap(): MetadataRoute.Sitemap {
  return ROUTES.flatMap((path) =>
    routing.locales.map((locale) => {
      // getPathname(locale-aware path) — the canonical routing wrapper
      // knows whether to prefix based on localePrefix: 'as-needed'.
      const localizedPath = getPathname({ locale, href: path })
      const url = `${SITE_URL}${localizedPath}`
      return {
        url,
        lastModified: new Date(),
        changeFrequency: 'daily',
        priority: path === '/' ? 1.0 : 0.7,
        alternates: {
          languages: Object.fromEntries(
            routing.locales.map((alt) => [
              alt,
              `${SITE_URL}${getPathname({ locale: alt, href: path })}`,
            ])
          ),
          // x-default points to the bare (default-locale) variant.
          canonical: url,
        },
      }
    })
  )
}
