'use client'

/**
 * DateRangeFilter — two native date inputs in a Popover.
 *
 * URL contract: `?from=<YYYY-MM-DD>&to=<YYYY-MM-DD>`. Empty fields
 * remove the key. Validation: `from <= to` if both set; the second
 * input refuses dates earlier than the first via the `min` attribute.
 *
 * Native `<input type="date">` was chosen over a calendar library
 * because the data range is a simple bounded interval for the MVP
 * (per the search MVP scope agreed with the user — calendar widgets
 * are P1).
 */

import * as React from 'react'
import { Calendar, X } from 'lucide-react'
import { useTranslations } from 'next-intl'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useFilterUrl } from '@/components/filters/useFilterUrl'

export interface DateRangeFilterProps {
  className?: string
}

export function DateRangeFilter({ className }: DateRangeFilterProps) {
  const t = useTranslations('Filters')
  const filters = useFilterUrl()
  const [open, setOpen] = React.useState(false)
  const from = filters.get('from') ?? ''
  const to = filters.get('to') ?? ''
  const hasValue = Boolean(from || to)

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className={cn(
            'w-full justify-between font-normal',
            !hasValue && 'text-muted-foreground',
            className
          )}
        >
          <span className="flex items-center gap-2 truncate">
            <Calendar className="h-4 w-4 opacity-70" />
            {hasValue ? `${from || '…'} → ${to || '…'}` : t('anyDate')}
          </span>
          {hasValue && (
            // span with role=button: same nested-button avoidance
            // as SourceFilter.tsx — the X is inside the PopoverTrigger.
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation()
                filters.reset(['from', 'to'])
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation()
                  e.preventDefault()
                  filters.reset(['from', 'to'])
                }
              }}
              className="ml-2 inline-flex cursor-pointer rounded p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={t('clearDate')}
            >
              <X className="h-3 w-3" />
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 space-y-3" align="start">
        <div className="space-y-1">
          <Label htmlFor="filter-from">{t('from')}</Label>
          <Input
            id="filter-from"
            type="date"
            value={from}
            max={to || undefined}
            onChange={(e) => filters.set('from', e.target.value || null)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="filter-to">{t('to')}</Label>
          <Input
            id="filter-to"
            type="date"
            value={to}
            min={from || undefined}
            onChange={(e) => filters.set('to', e.target.value || null)}
          />
        </div>
      </PopoverContent>
    </Popover>
  )
}
