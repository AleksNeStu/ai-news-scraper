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
 */

import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import type { Route } from 'next'
import { useCallback } from 'react'
import { cn } from '@/lib/utils'
import type { Tier } from '@ai-news-scraper/shared'

const TIER_ORDER: Tier[] = ['must_read', 'recommended', 'worth_a_look', 'low_priority']

const TIER_LABELS: Record<Tier | 'all', string> = {
  all: 'All',
  must_read: 'Must Read',
  recommended: 'Recommended',
  worth_a_look: 'Worth a Look',
  low_priority: 'Low Priority',
}

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
      const url = (qs ? `${pathname}?${qs}` : pathname) as Route
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
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by tier">
          <FilterChip
            label={TIER_LABELS.all}
            active={activeTier == null}
            onClick={() => onPickTier(null)}
          />
          {TIER_ORDER.map((t) => (
            <FilterChip
              key={t}
              label={TIER_LABELS[t]}
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
          aria-label="Group by tier"
        />
        Group by tier
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
        'rounded-full px-3 py-1 text-xs font-medium transition',
        active
          ? 'bg-primary text-primary-foreground'
          : 'bg-muted text-muted-foreground hover:text-foreground'
      )}
    >
      {label}
    </button>
  )
}
