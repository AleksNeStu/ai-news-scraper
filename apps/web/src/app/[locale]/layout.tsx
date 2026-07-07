import { NextIntlClientProvider, hasLocale } from 'next-intl'
import { setRequestLocale } from 'next-intl/server'
import { notFound } from 'next/navigation'
import { routing } from '@/i18n/routing'

/**
 * `[locale]` segment layout — the actual `<html>` + `<body>` owner (Task #32).
 *
 * This is the SKELETON delivered by the Architect. Frontend will fill
 * in the Sentry/Suspense/theme wrappers, but the next-intl primitives
 * are wired here so the build doesn't choke on missing imports.
 *
 * Key responsibilities:
 *   1. Validate the `locale` URL segment against `routing.locales`.
 *      Invalid locales → 404 via `notFound()`.
 *   2. Call `setRequestLocale(locale)` BEFORE any `useTranslations()`
 *      in the descendant tree so next-intl can resolve the message
 *      catalog on a static-rendered page (without it, prerendered
 *      pages log "MISSING_MESSAGE" at build time).
 *   3. Wrap children in `<NextIntlClientProvider>` so client components
 *      (NotificationBell, LoginPage form state, etc.) get the same
 *      message catalog the server components use.
 *   4. Emit `<html lang={locale}>` and preserve `className="dark"`
 *      from the original root layout.
 *
 * generateStaticParams returns both locales so Next can prerender
 * `/<route>` and `/ru/<route>` at build time. With `dynamicParams`
 * left at its default (true), an unlisted locale segment still 404s
 * via `notFound()` above.
 *
 * NOTE on `params`: Next.js 15 keeps `params` as a SYNCHRONOUS object
 * (the `Promise<{...}>` shape only lands in Next 16). When this app
 * upgrades to Next 16, the signature becomes
 *   `{ children, params }: { children, params: Promise<{ locale: string }> }`
 * and the body awaits `params`. Architect chose the sync form
 * deliberately to match the installed Next version.
 */
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: { locale: string }
}) {
  const { locale } = params

  if (!hasLocale(routing.locales, locale)) {
    notFound()
  }

  // MUST come before any `useTranslations` call in the tree.
  setRequestLocale(locale)

  return (
    <html lang={locale} className="dark">
      <body className="min-h-screen bg-background text-foreground antialiased">
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  )
}
