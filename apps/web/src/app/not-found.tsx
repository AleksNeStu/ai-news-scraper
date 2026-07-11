import Link from 'next/link'

/**
 * Root 404 page — rendered when the middleware isn't able to
 * redirect a bare path to its locale-prefixed form (e.g. the
 * static-prerender path in `next start --standalone`, or any
 * request that lands before the middleware's locale resolver
 * has a chance to run).
 *
 * The <html lang="en"> wrapper is REQUIRED for WCAG 2.1 / 2.2
 * 4.1.1 compliance: the global 404 page in Next.js 15 ships
 * without a lang attribute on <html>, and axe-core (the a11y CI
 * gate) flags that as a [serious] violation. Mirror the layout's
 * lang default so the 404 page renders consistently with the
 * app shell (default-locale strategy per `i18n/routing.ts`).
 *
 * The page also exposes a localised return-to-home link so the
 * user has somewhere to go after the 404 — the default Next
 * 404 is just a heading.
 */
export default function RootNotFound() {
  // `localePrefix: 'always'` means EVERY URL carries a locale segment.
  // The default-locale home renders at `/en` and Russian at `/ru`.
  // We hardcode `/en` because routing.defaultLocale is fixed at en in
  // this repo.
  const home = '/en'
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <main className="mx-auto flex max-w-xl flex-col items-center justify-center px-6 py-24 text-center">
          <h1 className="headline-serif text-4xl">Page not found</h1>
          <p className="mt-3 text-sm text-muted-foreground">
            The page you were looking for doesn&apos;t exist or has been moved.
          </p>
          <Link
            href={home as never}
            className="mt-8 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Back to home
          </Link>
        </main>
      </body>
    </html>
  )
}
