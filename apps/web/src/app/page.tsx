import { redirect } from 'next/navigation'
import { routing } from '@/i18n/routing'

/**
 * Root route shim — Task #53 + matrix-fix followup; revisited in Task #66.
 *
 * The web app uses ``next-intl`` with ``localePrefix: 'always'``,
 * so EVERY URL — including the default locale — must carry a locale
 * segment. The actual home page lives at ``app/[locale]/page.tsx``,
 * which only matches when the URL has a locale segment, so without
 * this shim ``GET /`` falls through to ``not-found.tsx`` and returns
 * 404. ``next-intl``'s middleware issues a 307 for bare paths, but a
 * server-side redirect from the root page component is the canonical
 * way to land the user on the default-locale home URL.
 *
 * Server-side redirect to the explicit ``/<defaultLocale>`` form
 * keeps the URL canonical and matches what the home link in
 * ``not-found.tsx`` (``href="/en"``) expects. For a non-default locale
 * the middleware (apps/web/middleware.ts) still applies, so e.g.
 * ``/ru`` is left alone.
 */
export default function RootPage(): never {
  redirect(`/${routing.defaultLocale}`)
}
