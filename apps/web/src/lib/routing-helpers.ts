/**
 * Locale-prefix helpers shared between the composed middleware and
 * unit tests (Task #66).
 *
 * These are intentionally plain functions (no Next.js / Edge runtime
 * imports) so they can be unit-tested under Node + vitest without
 * standing up the full Next.js dev server.
 *
 * Under ``localePrefix: 'always'`` (Task #66) EVERY locale gets the
 * ``/<locale>...`` form on the wire — including the default locale.
 * Before Task #66 the bare-path short-circuit for the default locale
 * was a source of an infinite redirect loop on the a11y CI gate.
 */

import { routing } from '@/i18n/routing'

// Strips a leading locale segment so the auth check in middleware.ts
// sees the canonical path the original (pre-i18n) middleware used.
//   '/en/dashboard'  → '/dashboard'
//   '/ru/login'      → '/login'
//   '/en'            → '/'
//   '/dashboard'     → '/dashboard'  (no locale — defensive fallback)
export function stripLocalePrefix(pathname: string): string {
  for (const locale of routing.locales) {
    if (pathname === `/${locale}`) return '/'
    if (pathname.startsWith(`/${locale}/`)) return pathname.slice(locale.length + 1)
  }
  return pathname
}

// Reverse helper: given a canonical path, return the locale-prefixed
// form for the requested active locale. Under `localePrefix: 'always'`
// EVERY locale — including the default — gets the `/<locale>...` form,
// so the bare-path short-circuit for the default locale is removed.
//   withLocalePrefix('/login', 'en') → '/en/login'
//   withLocalePrefix('/login', 'ru') → '/ru/login'
//   withLocalePrefix('/', 'en')      → '/en'
//   withLocalePrefix('/', 'ru')      → '/ru'
export function withLocalePrefix(canonical: string, activeLocale: string): string {
  return `/${activeLocale}${canonical === '/' ? '' : canonical}`
}
