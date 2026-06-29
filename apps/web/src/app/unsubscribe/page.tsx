import { Suspense } from 'react'
import UnsubscribeForm from './UnsubscribeForm'

/**
 * One-click unsubscribe landing page (RFC 8058 §3.2).
 *
 * Server Component that wraps the client form in <Suspense> so that
 * Next.js 15's useSearchParams() prerender rule is satisfied:
 * https://nextjs.org/docs/messages/missing-suspense-with-csr-bailout
 *
 * The actual logic lives in UnsubscribeForm (client component) because
 * it calls hooks (useSearchParams, useState, useEffect).
 */
export default function UnsubscribePage() {
  return (
    <Suspense fallback={<UnsubscribeFallback />}>
      <UnsubscribeForm />
    </Suspense>
  )
}

function UnsubscribeFallback() {
  return (
    <main className="min-h-screen">
      <div className="mx-auto flex max-w-md flex-col items-center px-6 py-20 text-center">
        <p className="text-sm text-muted-foreground">Loading…</p>
      </div>
    </main>
  )
}
