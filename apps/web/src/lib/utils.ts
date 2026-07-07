import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Locale-aware date/relative-time helpers (Task #32).
 *
 * Both functions accept an optional `locale` (BCP-47 tag, e.g. `'en'` /
 * `'ru'`). When omitted, they fall back to the runtime default (browser
 * locale on the client; `undefined` ⇒ Node's default on the server) so
 * existing callers that don't pass a locale keep working.
 *
 * The implementation uses the platform `Intl.*` constructors directly
 * rather than next-intl's `useFormatter`/`getFormatter` because these
 * helpers are called from BOTH server components (where `getFormatter`
 * works) AND non-component server code (lib/api error classes,
 * notification factories, etc.) where the next-intl context isn't
 * available. Direct `Intl` is the right primitive for that surface.
 *
 * Time math stays in milliseconds; locale formatting is the only thing
 * the locale parameter affects. The relative thresholds
 * (<1m / <1h / <1d / <7d) match the previous English behavior so
 * switching locale doesn't change WHEN the format switches, only HOW
 * the resulting text reads.
 */

/**
 * Format an ISO date string as a short, locale-aware date.
 *
 *   formatDate('2026-03-05', 'en') → "Mar 5, 2026"
 *   formatDate('2026-03-05', 'ru') → "5 мар. 2026 г."
 *
 * Returns the dash placeholder (`'—'`) for null/undefined input so callers
 * don't have to guard the empty case inline.
 */
export function formatDate(iso: string | null | undefined, locale?: string): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    }).format(new Date(iso))
  } catch {
    // Invalid date string — fall back to the raw input rather than crash.
    return iso
  }
}

/**
 * Format an ISO date string as a long, locale-aware date including weekday.
 *
 *   formatLongDate('2026-03-05', 'en') → "Tuesday, March 5, 2026"
 *   formatLongDate('2026-03-05', 'ru') → "вторник, 5 марта 2026 г."
 *
 * Used by the brief detail page and the unsubscribe success card.
 */
export function formatLongDate(iso: string | null | undefined, locale?: string): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat(locale, {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

/**
 * Format an ISO timestamp as a locale-aware date + short time.
 *
 *   formatTimestamp('2026-03-05T08:00:00Z', 'en') → "Mar 5, 2026, 8:00 AM"
 *   formatTimestamp('2026-03-05T08:00:00Z', 'ru') → "5 мар. 2026 г., 08:00"
 *
 * Used by the unsubscribe success card.
 */
export function formatTimestamp(iso: string | null | undefined, locale?: string): string {
  if (!iso) return '—'
  try {
    return new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

/**
 * Format a "time since" string in the active locale.
 *
 *   formatRelative(t, 'en') → "just now" / "5m ago" / "2h ago" / "3d ago" / "Mar 5"
 *   formatRelative(t, 'ru') → "только что" / "5 мин назад" / "2 ч назад" / "3 дн назад" / "5 мар."
 *
 * The bucketing thresholds are locale-independent — they're how the
 * relative-time vocabulary switches from "X minutes ago" to "X hours
 * ago", which is a semantic decision (not a localization one).
 */
export function formatRelative(iso: string | null | undefined, locale?: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const diff = Date.now() - d.getTime()
  const min = 60_000,
    hour = 60 * min,
    day = 24 * hour
  if (diff < min) return formatRelativeUnit(locale, 'just-now')
  if (diff < hour) return formatRelativeUnit(locale, 'minutes', Math.floor(diff / min))
  if (diff < day) return formatRelativeUnit(locale, 'hours', Math.floor(diff / hour))
  if (diff < 7 * day) return formatRelativeUnit(locale, 'days', Math.floor(diff / day))
  return formatDate(iso, locale)
}

/**
 * Internal: turn a relative-time bucket into the localized "X ago" /
 * "только что" phrase via ICU-friendly string templates keyed off the
 * active locale. Splitting the unit table out keeps `formatRelative`
 * readable while keeping all locale strings in one place.
 *
 * The `numeric: 'always'` setting ensures we always render a number
 * (e.g. "1 minute ago", "1 минуту назад") rather than the word "one"
 * — matches the previous English hand-rolled output.
 */
function formatRelativeUnit(
  locale: string | undefined,
  unit: 'just-now' | 'minutes' | 'hours' | 'days',
  value?: number
): string {
  const tag = locale ?? 'en'
  const rtf = new Intl.RelativeTimeFormat(tag, { numeric: 'always' })
  const map = {
    minutes: 'minute',
    hours: 'hour',
    days: 'day',
  } as const
  if (unit === 'just-now') {
    // English: "now" / Russian: "только что" / German: "jetzt" / etc.
    // `numeric: 'auto'` lets Intl produce the locale-appropriate word
    // for the present-tense zero-second offset — replaces the prior
    // `tag.startsWith('ru') ? 'только что' : 'just now'` ternary
    // (Devil-6 finding: adding a third locale required editing code).
    return new Intl.RelativeTimeFormat(tag, { numeric: 'auto' }).format(0, 'second')
  }
  return rtf.format(-(value ?? 0), map[unit])
}
