/**
 * Site-specific JSON-LD factory functions (Task #28 Frontend half).
 *
 * Wraps the Architect's strict, serializable interfaces
 * (`packages/shared/src/structured-data.ts`) with values that belong to
 * this app: SITE_URL, SITE_NAME, locale, canonical paths. The Architect's
 * types forbid `null` for optional fields and require a JSON-serializable
 * shape (no Date, no functions, no `undefined`), so every optional field
 * is emitted via conditional spread — never `"image": null`.
 *
 * Adding a schema:
 *   1. Add the interface to `packages/shared/src/structured-data.ts`.
 *   2. Add a builder here that fills in the site-specific values.
 *   3. Call the builder from the route's server component and feed the
 *      result into `<StructuredData>`.
 *
 * Notes:
 *   - `mainEntityOfPage` and `BreadcrumbList.item` are absolute URLs —
 *     build them from `SITE_URL + canonicalPath`, where `canonicalPath`
 *     comes from `getPathname({ locale, href })` so the path respects
 *     `localePrefix: 'always'` (both `en` and `ru` get a `/<locale>`
 *     prefix — no bare default-locale URL).
 *   - `inLanguage` always matches the active route segment.
 *   - SearchAction `urlTemplate` always points at the `/search` route in
 *     the requested locale.
 */

import { SITE_URL } from '@/lib/site'
import { getPathname } from '@/i18n/navigation'
import type {
  BreadcrumbList,
  CollectionPage,
  Organization,
  SoftwareApplication,
  WebSite,
} from '@ai-news-scraper/shared'
import type { ArticleJsonLd as ArticleLd } from '@ai-news-scraper/shared/src/structured-data'

/**
 * Project display name. Centralized so the Organization, WebSite, and
 * SoftwareApplication builders never disagree.
 */
export const SITE_NAME = 'ai-news-scraper'

/**
 * One-paragraph marketing description. Surfaced as the `description`
 * field of every site-wide JSON-LD node and as `og:description` /
 * `twitter:description` in the corresponding Metadata blocks. Edit here
 * once; every consumer picks it up.
 */
export const SITE_DESCRIPTION =
  'AI-powered news briefing app: scrape, summarize, and semantically search articles with a personal feed of curated headlines.'

/**
 * Build the Organization JSON-LD. The Architect leaves `logo` and
 * `sameAs` undefined by contract; populate them when those assets ship.
 */
export function buildOrganizationJsonLd(): Organization {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: SITE_NAME,
    url: SITE_URL,
    description: SITE_DESCRIPTION,
  }
}

/**
 * Build the WebSite JSON-LD for the given locale. The `potentialAction`
 * points at the locale-aware `/search` route.
 */
export function buildWebSiteJsonLd(locale: 'en' | 'ru'): WebSite {
  const searchPath = getPathname({ locale, href: '/search' })
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: SITE_NAME,
    url: SITE_URL,
    inLanguage: locale,
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${SITE_URL}${searchPath}?q={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  }
}

/**
 * Build the SoftwareApplication JSON-LD for the `/dashboard` landing
 * surface. Free price point, web-only target per current distribution.
 */
export function buildSoftwareApplicationJsonLd(): SoftwareApplication {
  return {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: SITE_NAME,
    url: SITE_URL,
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    description: SITE_DESCRIPTION,
    offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
  }
}

/**
 * Build the Article JSON-LD for the detail page. `canonicalPath` is the
 * locale-internal path (e.g. `/articles/<id>`); the builder combines
 * with `SITE_URL` to produce `mainEntityOfPage`. Optional fields use
 * conditional spread so the Architect's strict types hold.
 */
export function buildArticleJsonLd(args: {
  id: string
  headline: string
  datePublished: string
  dateModified?: string
  description?: string
  image?: string
  author?: string
  keywords?: string
  locale: 'en' | 'ru'
  canonicalPath: string
}): ArticleLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: args.headline,
    datePublished: args.datePublished,
    ...(args.dateModified ? { dateModified: args.dateModified } : {}),
    ...(args.author ? { author: args.author } : {}),
    ...(args.image ? { image: args.image } : {}),
    mainEntityOfPage: `${SITE_URL}${args.canonicalPath}`,
    inLanguage: args.locale,
    ...(args.description ? { description: args.description } : {}),
    ...(args.keywords ? { keywords: args.keywords } : {}),
  }
}

/**
 * Build a BreadcrumbList from a small array of `{ name, path }` pairs.
 * `path` is the locale-internal path; the builder prefixes `SITE_URL`.
 * Position is 1-based ordinal per Schema.org convention.
 */
export function buildBreadcrumbJsonLd(crumbs: { name: string; path: string }[]): BreadcrumbList {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: crumbs.map((c, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: c.name,
      item: `${SITE_URL}${c.path}`,
    })),
  }
}

/**
 * Build a CollectionPage JSON-LD for the `/articles` index.
 */
export function buildCollectionPageJsonLd(args: {
  name: string
  description?: string
  locale: 'en' | 'ru'
  canonicalPath: string
}): CollectionPage {
  return {
    '@context': 'https://schema.org',
    '@type': 'CollectionPage',
    name: args.name,
    url: `${SITE_URL}${args.canonicalPath}`,
    ...(args.description ? { description: args.description } : {}),
    inLanguage: args.locale,
  }
}
