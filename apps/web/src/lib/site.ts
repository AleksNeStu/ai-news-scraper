/**
 * Canonical site URL (Task #32 polish, Devil-7).
 *
 * Reads NEXT_PUBLIC_SITE_URL at request time so the same code emits
 * absolute URLs in dev (localhost:3807, per nest-solo's
 * PORT_REGISTRY.json externalLocal.ai-news-scraper), staging, and
 * production without a rebuild. The trailing-slash strip keeps the
 * resulting paths joinable with a single `/` separator.
 *
 * Used by:
 *   - app/sitemap.ts (every per-locale entry's `url` + `alternates.languages`)
 *   - app/[locale]/layout.tsx (`generateMetadata` hreflang block)
 *
 * Adding a new caller means `import { SITE_URL } from '@/lib/site'`,
 * not a third duplicate of the localhost fallback.
 */
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL?.replace(/\/$/, '') || 'http://localhost:3807'
