'use client'

/**
 * Client UI for /articles: tier filter chips and a "Group by tier" toggle.
 *
 * The Server Component above fetches and renders cards; this component
 * just owns the URL-bound filter state via `router.replace`.
 *
 *   - `?tier=must_read`           → tier filter
 *   - `?group_by_tier=true`       → grouped mode (chips hidden, 4 sections)
 *
 * Tier chips and the toggle both push via `router.replace` so the back
 * button isn't filled with intermediate filter steps.
 *
 * i18n (Task #32): chip labels + ARIA labels come from
 * `useTranslations('Tiers')` / `useTranslations('Articles')`. The
 * router comes from `@/i18n/navigation` so the locale-aware wrapper
 * preserves the active locale on every URL change.
 */

import { usePathname, useRouter, useSearchParams } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { useCallback } from 'react'
import { cn } from '@/lib/utils'
import type { Tier } from '@ai-news-scraper/shared'

const TIER_ORDER: Tier[] = ['must_read', 'recommended', 'worth_a_look', 'low_priority']

export function ArticlesToolbar({
  activeTier,
  grouped,
}: {
  activeTier: Tier | null
  grouped: boolean
}) {
  const router = useRouter()
  const pathname = usePathname()
  const search = useSearchParams()
  const tTiers = useTranslations('Tiers')
  const tArticles = useTranslations('Articles')

  const setParams = useCallback(
    (next: Record<string, string | null>) => {
      const params = new URLSearchParams(search?.toString() ?? '')
      for (const [k, v] of Object.entries(next)) {
        if (v == null) params.delete(k)
        else params.set(k, v)
      }
      const qs = params.toString()
      // typedRoutes requires a known Route literal; the dynamic
      // `pathname` + querystring is not statically known, so we cast.
      // Safe because the pathname comes from usePathname() — the typed
      // routes feature only blocks bogus strings, not real ones.
      const url = (qs ? `${pathname}?${qs}` : pathname) as never
      router.replace(url, { scroll: false })
    },
    [router, pathname, search]
  )

  // Reset pagination on filter / view change — staying on page 2 of an
  // empty filtered set is a UX bug (Devil M#1, Task #9 review).
  const onPickTier = (tier: Tier | null) => {
    setParams({ tier: tier, page: null })
  }
  const onToggleGrouped = () => {
    setParams({ group_by_tier: grouped ? null : 'true', page: null })
  }

  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      {!grouped && (
        <div
          className="flex flex-wrap items-center gap-2"
          role="group"
          aria-label={tArticles('filterGroupLabel')}
        >
          <FilterChip
            label={tTiers('all')}
            active={activeTier == null}
            onClick={() => onPickTier(null)}
          />
          {TIER_ORDER.map((t) => (
            <FilterChip
              key={t}
              label={tTiers(tierKey(t))}
              active={activeTier === t}
              onClick={() => onPickTier(t)}
            />
          ))}
        </div>
      )}
      <label className="ml-auto inline-flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
        <input
          type="checkbox"
          checked={grouped}
          onChange={onToggleGrouped}
          className="h-4 w-4 cursor-pointer rounded border-border bg-canvas accent-primary"
          aria-label={tArticles('groupByTierLabel')}
        />
        {tArticles('groupByTierLabel')}
      </label>
    </div>
  )
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        // WCAG 2.5.8 (target-size, AA) needs >= 24x24 CSS px for
        // interactive controls. We pad generously (h-10 w-10 plus
        // px-4 py-2) so a single-tier chip (~3 chars in the tier
        // name) renders at 40x40 -- well above the minimum. text-xs
        // keeps the visual rhythm tight while the tap area stays
        // generous. min-h-10 + min-w-10 belt-and-braces against
        // flex-shrink in the surrounding Toolbar.
        'inline-flex items-center justify-center min-h-10 min-w-10 px-4 py-2 text-xs font-medium rounded-full transition',
        active
          ? 'bg-primary text-primary-foreground'
          : 'bg-muted text-muted-foreground hover:text-foreground'
      )}
    >
      {label}
    </button>
  )
}

/** Map a Tier enum → catalog key in the `Tiers` namespace. */
function tierKey(t: Tier): 'mustRead' | 'recommended' | 'worthALook' | 'lowPriority' {
  switch (t) {
    case 'must_read':
      return 'mustRead'
    case 'recommended':
      return 'recommended'
    case 'worth_a_look':
      return 'worthALook'
    case 'low_priority':
      return 'lowPriority'
  }
}
