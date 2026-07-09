import { Suspense } from 'react'
import { notFound } from 'next/navigation'
import type { Metadata } from 'next'
import { hasLocale } from 'next-intl'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import { routing } from '@/i18n/routing'
import { EmbeddingsView } from './EmbeddingsView'
import { EmbeddingsSkeleton } from './EmbeddingsSkeleton'

/**
 * /embeddings page (Task #34, ADR-022).
 *
 * Server Component shell that:
 *   1. Validates the active locale against `routing.locales` (the parent
 *      `[locale]` layout does this too; we re-check defensively per the
 *      pattern in `[locale]/s/[token]/page.tsx`).
 *   2. Emits noindex metadata — this is an internal tooling page, not a
 *      marketing surface. Search engines + AI crawlers should not index
 *      it; we also don't need hreflang alternates for it.
 *   3. Renders `<EmbeddingsView />` (the client island) inside a
 *      `<Suspense>` boundary so the page test can mount just the island
 *      without driving the server-rendered shell (Next.js Server
 *      Components can't be unit-rendered in jsdom).
 *
 * The `(app)` route group supplies the auth-required layout (header +
 * skip-link + main landmark) — this page inherits it automatically.
 */

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string }>
}): Promise<Metadata> {
  // Per ADR-022 — internal tool, must not be indexed. We don't need
  // the locale here (no localised title), but the param is required by
  // Next's generateMetadata signature; discard with void to satisfy
  // `no-unused-vars`.
  void params
  return {
    title: 'Embedding playground',
    robots: { index: false, follow: false },
  }
}

export default async function EmbeddingsPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale: rawLocale } = await params
  if (!hasLocale(routing.locales, rawLocale)) notFound()
  const locale = rawLocale as 'en' | 'ru'
  setRequestLocale(locale)
  const t = await getTranslations('Embeddings')

  return (
    <div className="mx-auto max-w-6xl">
      <header className="border-b border-border px-6 py-6">
        <h1 className="text-2xl font-semibold headline-serif">{t('pageTitle')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('pageDescription')}</p>
      </header>
      <Suspense fallback={<EmbeddingsSkeleton />}>
        <EmbeddingsView />
      </Suspense>
    </div>
  )
}
