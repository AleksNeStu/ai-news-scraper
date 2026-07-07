import { Suspense } from 'react'
import { getTranslations, setRequestLocale } from 'next-intl/server'
import UnsubscribeForm from './UnsubscribeForm'

/**
 * One-click unsubscribe landing page (RFC 8058 §3.2 + Task #32).
 *
 * Server Component that wraps the client form in <Suspense> so that
 * Next.js 15's useSearchParams() prerender rule is satisfied:
 * https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout
 *
 * The actual logic lives in UnsubscribeForm (client component) because
 * it calls hooks (useSearchParams, useState, useEffect).
 *
 * i18n (Task #32): the fallback "Loading…" copy now flows from the
 * `Common` namespace via `getTranslations`.
 */
export default async function UnsubscribePage({
  params,
}: {
  params: { locale: string }
}) {
  const { locale } = params
  setRequestLocale(locale)
  const t = await getTranslations('Common')
  return (
    <Suspense fallback={<UnsubscribeFallback loading={t('loading')} />}>
      <UnsubscribeForm />
    </Suspense>
  )
}

function UnsubscribeFallback({ loading }: { loading: string }) {
  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <p className="text-sm text-muted-foreground">{loading}</p>
      </div>
    </main>
  )
}