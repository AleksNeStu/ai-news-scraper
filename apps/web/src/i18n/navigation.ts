import { createNavigation } from 'next-intl/navigation'
import { routing } from './routing'

/**
 * Locale-aware navigation primitives (Task #32).
 *
 * Every consumer in the app must import `Link`, `redirect`,
 * `usePathname`, `useRouter`, and `getPathname` from `@/i18n/navigation`
 * — never directly from `next/navigation`. The wrapped versions know
 * about the `[locale]` segment and auto-prefix the active locale (or
 * strip it for the default `en` locale).
 *
 * Why a single re-export:
 *   - One place to change routing implementation later (e.g. swapping
 *     `next-intl` for another lib).
 *   - Static analysis can grep `@/i18n/navigation` to find every
 *     navigation call site that needs to be locale-aware.
 *   - The wrapped `Link` component also emits `hreflang` alternates on
 *     SSR when `alternateLinks: true` is set in `routing.ts`.
 */
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing)
