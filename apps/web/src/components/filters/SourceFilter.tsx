'use client'

/**
 * SourceFilter — single-select combobox over the runtime-distinct
 * `Article.source_domain` values.
 *
 * The MVP ships with a small static option list as a stand-in; once
 * `GET /search/facets` lands in Track B the `options` prop will be
 * wired to the live endpoint and the count annotations can be added.
 *
 * URL contract: `?source=<domain>`. Empty selection removes the key.
 *
 * Accessibility:
 *   - Trigger renders as a `<button role="combobox">` with
 *     aria-expanded + aria-controls.
 *   - Command list keyboard nav (cmdk) handles up/down/enter.
 *   - Clear button is `aria-label="Clear selection"`.
 */

import * as React from 'react'
import { Check, ChevronsUpDown, X } from 'lucide-react'
import { useTranslations } from 'next-intl'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { useFilterUrl } from '@/components/filters/useFilterUrl'

export interface SourceFilterProps {
  /** Available source_domain values (e.g. ['techcrunch.com', 'theverge.com']). */
  options: string[]
  className?: string
  /** Placeholder rendered when nothing is selected. */
  placeholder?: string
}

export function SourceFilter({
  options,
  className,
  placeholder = 'All sources',
}: SourceFilterProps) {
  const t = useTranslations('Filters')
  const filters = useFilterUrl()
  const [open, setOpen] = React.useState(false)
  const triggerId = React.useId()
  const listId = `${triggerId}-list`

  const selected = filters.get('source')

  function pick(value: string | null) {
    filters.set('source', value)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          id={triggerId}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-controls={listId}
          className={cn('w-full justify-between font-normal', className)}
        >
          <span className={cn('truncate', !selected && 'text-muted-foreground')}>
            {selected ?? placeholder}
          </span>
          {selected ? (
            // Use a span with role=button (not a <button>) because the
            // X is nested inside the PopoverTrigger button. Nested
            // <button> is invalid HTML and browsers split the click
            // target in unpredictable ways. role=button keeps the
            // affordance for AT and keyboard (Enter/Space).
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => {
                e.stopPropagation()
                pick(null)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation()
                  e.preventDefault()
                  pick(null)
                }
              }}
              className="ml-2 inline-flex cursor-pointer rounded p-0.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              aria-label={t('clearSource')}
            >
              <X className="h-3 w-3" />
            </span>
          ) : (
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder={t('searchSources')} />
          <CommandList>
            <CommandEmpty>{t('noSources')}</CommandEmpty>
            <CommandGroup>
              {options.map((domain) => (
                <CommandItem
                  key={domain}
                  value={domain}
                  onSelect={() => pick(domain)}
                  role="option"
                  aria-selected={selected === domain}
                >
                  <Check
                    className={cn(
                      'mr-2 h-4 w-4',
                      selected === domain ? 'opacity-100' : 'opacity-0'
                    )}
                  />
                  {domain}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
