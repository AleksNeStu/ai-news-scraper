import { Suspense } from 'react'
import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import { hasLocale } from 'next-intl'
import { ShareView } from './ShareView'
import { ShareSkeleton } from './ShareSkeleton'
import { routing } from '@/i18n/routing'

/**
 * Public share page (Task #33, ADR-021 §21.5).
 *
 * Route shape: `/[locale]/s/[token]`. The locale segment uses the same
 * routing.locales union ('en' | 'ru') as the rest of the app; if the
 * caller lands here with an unsupported locale, the parent `[locale]`
 * layout calls `notFound()`. The token itself is locale-agnostic.
 *
 * i18n fallback (ADR-021 §21.5): in v1 the only shipped locales are
 * `en` and `ru`, so there is no third-locale fallback yet. When `de`
 * arrives, the recommendation is to render English copy rather than
 * 404, since the snapshot is shared; the `routing.locales` allow-list
 * will be updated as part of that work, not here.
 *
 * Noindex (ADR-021 §21.4): the page's <head> ships
 * `robots: { index: false, follow: false }` so search engines do not
 * index user-shared snapshots. The `X-Robots-Tag: noindex` HTTP header
 * is emitted by the FastAPI handler for the data fetch; this metadata
 * complements that for the page-rendered shell.
 *
 * Suspense + skeleton: the actual data fetch lives in the client
 * `<ShareView />` so we can show error / gone states without crashing
 * the server render. The Suspense boundary is required to keep
 * Next.js happy with the prerender rule for client hooks
 * (`useTranslations`, `useLocale`).
 */

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; token: string }>
}): Promise<Metadata> {
  const { token } = await params
  // Token intentionally excluded from <title>: never echo secrets into
  // document.title where a screen reader or share-sheet preview might
  // surface it.
  void token
  return {
    robots: { index: false, follow: false },
    title: 'Shared article',
  }
}

export default async function SharedArticlePage({
  params,
}: {
  params: Promise<{ locale: string; token: string }>
}) {
  const { locale: rawLocale, token } = await params
  // The parent [locale] layout has already validated `rawLocale` against
  // routing.locales; we re-check defensively so this route is safe even
  // if it is ever lifted out of the [locale] subtree.
  if (!hasLocale(routing.locales, rawLocale)) notFound()
  if (!token) notFound()

  const locale = rawLocale as 'en' | 'ru'
  setRequestLocale(locale)
  await getTranslations('Share.View') // warm the catalog for static-prerender

  return (
    <Suspense fallback={<ShareSkeleton />}>
      <ShareView token={token} />
    </Suspense>
  )
}
