import { redirect } from 'next/navigation'
import { routing } from '@/i18n/routing'

/**
 * Root route shim — Task #53 + matrix-fix followup.
 *
 * The web app uses ``next-intl`` with ``localePrefix: 'as-needed'``,
 * so the default locale (``en``) is meant to be reachable at the bare
 * ``/`` URL. The actual page lives at ``app/[locale]/page.tsx``, which
 * only matches when the URL has a locale segment, so without this
 * shim ``GET /`` falls through to ``not-found.tsx`` and returns 404.
 * next-intl's middleware does not auto-rewrite the bare ``/`` path to
 * ``/en`` for the root dynamic-segment route.
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
