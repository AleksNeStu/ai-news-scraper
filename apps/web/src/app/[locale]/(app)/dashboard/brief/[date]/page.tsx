/**
 * /dashboard/brief/[date] — server-component shell for the daily Brief
 * detail page (Task #32 + Task #28 Frontend half).
 *
 * The actual interactive tree is owned by `DigestDetailClient`
 * (same folder), driven by `useDigest(date)`. This shell exists so
 * App-Router `generateMetadata` and JSON-LD injection run server-side
 * — a `'use client'` page cannot emit `<script type="application/ld+json">`
 * in the initial HTML, so we split:
 *
 *   page.tsx (server)
 *     ├── <StructuredData data={BreadcrumbList + canonical meta}>
 *     └── <DigestDetailClient />  ← the old client component
 *
 * The validated `date` is read on the server and passed to the client
 * tree via URL params (the client component re-reads it from
 * `useParams()` to keep the existing `useDigest(date)` wiring intact).
 */

import type { Metadata } from 'next'
import { getPathname } from '@/i18n/navigation'
import { SITE_URL } from '@/lib/site'
import { StructuredData } from '@/components/StructuredData'
import { buildBreadcrumbJsonLd } from '@/lib/structured-data/builders'
import DigestDetailClient from './DigestDetailClient'

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/

/**
 * Page metadata (Task #28): canonical + og:* + twitter:*. The brief
 * detail page is dynamic per date, so `alternates.canonical` carries
 * the full date path. `title` falls back to the raw date string so
 * an invalid / missing brief still has a parseable document title.
 */
export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string; locale: string }>
}): Promise<Metadata> {
  const { date, locale } = await params
  const path = DATE_RE.test(date) ? `/dashboard/brief/${date}` : '/dashboard/brief'
  const canonical = `${SITE_URL}${getPathname({ locale: locale as 'en' | 'ru', href: path })}`
  const title = `Brief — ${date}`
  return {
    title,
    alternates: { canonical },
    openGraph: {
      title,
      type: 'article',
      url: canonical,
      siteName: 'ai-news-scraper',
      locale: locale === 'en' ? 'en_US' : 'ru_RU',
    },
    twitter: {
      card: 'summary_large_image',
      title,
    },
  }
}

export default async function DigestDetailPage({
  params,
}: {
  params: Promise<{ date: string; locale: string }>
}) {
  const { date, locale } = await params

  const valid = DATE_RE.test(date)
  const detailPath = valid
    ? getPathname({ locale: locale as 'en' | 'ru', href: `/dashboard/brief/${date}` })
    : getPathname({ locale: locale as 'en' | 'ru', href: '/dashboard/brief' })

  return (
    <>
      {/* GEO readiness (Task #28): BreadcrumbList gives the
          Home → Dashboard → Brief → <date> trail. The last crumb
          reuses the detail URL on a valid date, or falls back to the
          Brief index when the date segment doesn't match `YYYY-MM-DD`. */}
      <StructuredData
        data={buildBreadcrumbJsonLd([
          { name: 'Home', path: getPathname({ locale: locale as 'en' | 'ru', href: '/' }) },
          {
            name: 'Dashboard',
            path: getPathname({ locale: locale as 'en' | 'ru', href: '/dashboard' }),
          },
          {
            name: 'Brief',
            path: getPathname({ locale: locale as 'en' | 'ru', href: '/dashboard/brief' }),
          },
          ...(valid ? [{ name: date, path: detailPath }] : []),
        ])}
      />
      <DigestDetailClient />
    </>
  )
}
