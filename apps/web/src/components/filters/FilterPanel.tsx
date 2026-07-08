'use client'

/**
 * FilterPanel — composes the three filter widgets (Source, Topics,
 * Date) into a single accessible region. Used as the sidebar on
 * `/search` (Track B) and any future filtered list page.
 *
 * Pure composition: each widget owns its own URL key + state. The
 * panel just provides the labelled landmark + layout. New widgets
 * can be added by appending to the children or wrapping with a
 * labelled <section>.
 *
 * For MVP, the panel is a 1-column stack; future iterations can
 * switch to a 2-column responsive grid.
 */

import * as React from 'react'

import { SourceFilter } from '@/components/filters/SourceFilter'
import { TopicMultiSelect, type TopicMultiSelectProps } from '@/components/filters/TopicMultiSelect'
import { DateRangeFilter } from '@/components/filters/DateRangeFilter'

export interface FilterPanelProps {
  /** Static or live list of `source_domain` values to populate SourceFilter. */
  sources: string[]
  /** Topic options for the multi-select (label, value pairs). */
  topics: TopicMultiSelectProps['options']
  /** Aria label for the panel landmark. Defaults to "Filters". */
  label?: string
  className?: string
}

export function FilterPanel({ sources, topics, label = 'Filters', className }: FilterPanelProps) {
  return (
    <aside aria-label={label} className={className}>
      <div className="space-y-3">
        <SourceFilter options={sources} />
        <TopicMultiSelect options={topics} />
        <DateRangeFilter />
      </div>
    </aside>
  )
}
