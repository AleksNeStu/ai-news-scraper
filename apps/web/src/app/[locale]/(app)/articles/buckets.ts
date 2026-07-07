/**
 * Pure helpers extracted from `articles/page.tsx` so they can be unit-tested
 * without standing up a Next.js server-component render in jsdom.
 *
 * Keeping them in a separate file (no `"use server"` / `"use client"` directive)
 * means both the Server Component and the test suite can `import` them.
 *
 * Note on i18n (Task #32): the tier order / grouping / `isTier` helpers are
 * pure-data and locale-independent, so they stay here unchanged. The actual
 * tier labels are resolved at render time via `useTranslations('Tiers')` in
 * the page — collapsing the three prior `TIER_HEADINGS` maps into a single
 * message catalog entry.
 */

import type { Article, Tier } from '@ai-news-scraper/shared'

export const TIER_ORDER: readonly Tier[] = [
  'must_read',
  'recommended',
  'worth_a_look',
  'low_priority',
]

export function isTier(v: unknown): v is Tier {
  return typeof v === 'string' && (TIER_ORDER as readonly string[]).includes(v)
}

/** Group articles into tier buckets, preserving insertion order within a bucket. */
export function bucketByTier(items: Article[]): Record<Tier, Article[]> {
  const out: Record<Tier, Article[]> = {
    must_read: [],
    recommended: [],
    worth_a_look: [],
    low_priority: [],
  }
  for (const a of items) {
    if (a.tier && out[a.tier]) out[a.tier].push(a)
  }
  return out
}
