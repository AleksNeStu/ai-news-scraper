'use client'

/**
 * TopicMultiSelect — multi-select over `Article.topics[]`.
 *
 * URL contract: `?topic=a&topic=b` (repeatable key). Reading uses
 * `useFilterUrl.getAll('topic')`; writing goes through `remove`
 * (per-value) and `append` (add-value).
 *
 * Note: in production the `topics` column is empty today (see
 * `apps/api/api/routers/scrape.py:69` — extracted as P1 work). The
 * widget still ships so the `/search` filter UI has the affordance
 * ready when the topic extractor lands.
 */

import { useFilterUrl } from '@/components/filters/useFilterUrl'
import { MultiSelect, type MultiSelectOption } from '@/components/ui/multi-select'

export interface TopicMultiSelectProps {
  options: MultiSelectOption[]
  className?: string
}

export function TopicMultiSelect({ options, className }: TopicMultiSelectProps) {
  const filters = useFilterUrl()
  const value = filters.getAll('topic')

  return (
    <MultiSelect
      options={options}
      value={value}
      onValueChange={(next) => {
        // The hook's URL-bound setter is the source of truth for what the
        // URL looks like; align the URL state with the controlled change.
        const before = new Set(value)
        const after = new Set(next)
        for (const v of before) {
          if (!after.has(v)) filters.remove('topic', v)
        }
        for (const v of after) {
          if (!before.has(v)) filters.append('topic', v)
        }
      }}
      className={className}
      placeholder="All topics"
      searchPlaceholder="Search topics…"
      emptyMessage="No topics."
    />
  )
}
