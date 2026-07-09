'use client'

/**
 * Multi-select primitive composed from shadcn `Popover` + `Command`.
 *
 * shadcn does not ship a multi-select out of the box; this is the
 * canonical recipe (Popover trigger + Command list with checkable
 * items). It is the smallest viable component that:
 *
 *   - Renders a trigger button summarizing the current selection
 *     ("All", a comma-joined list, or a count).
 *   - Opens a popover with a Command list. Each option is a
 *     checkable item; clicking toggles it via the controlled
 *     `value`/`onValueChange` API.
 *   - Surfaces the accessible state: aria-expanded, aria-controls,
 *     role=listbox on the option list.
 *
 * Per DESIGN.md §6 (borders-only, no shadows) the popover inherits
 * the `PopoverContent` styling installed under Task #44, which has
 * had its `shadow-md` literal stripped.
 *
 * Selection rendering: at most 2 visible labels in the trigger
 * ("a, b +N more"); empty selection renders a localized placeholder.
 * Adjust the `summary` callback to control the chip style.
 */

import * as React from 'react'
import { Check, ChevronDown, X } from 'lucide-react'

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

export interface MultiSelectOption {
  value: string
  label: string
}

export interface MultiSelectProps {
  options: MultiSelectOption[]
  value: string[]
  onValueChange: (next: string[]) => void
  placeholder?: string
  searchPlaceholder?: string
  emptyMessage?: string
  /** Maximum labels to render in the trigger before collapsing to "+N more". */
  maxLabels?: number
  className?: string
  disabled?: boolean
  id?: string
}

export function MultiSelect({
  options,
  value,
  onValueChange,
  placeholder = 'Select…',
  searchPlaceholder = 'Search…',
  emptyMessage = 'No matches.',
  maxLabels = 2,
  className,
  disabled,
  id,
}: MultiSelectProps) {
  const [open, setOpen] = React.useState(false)
  // useId() must run unconditionally on every render; pick the
  // caller-supplied id afterwards. `id ?? React.useId()` would
  // short-circuit the hook call and trip react-hooks/rules-of-hooks.
  const generatedId = React.useId()
  const triggerId = id ?? generatedId
  const listId = `${triggerId}-list`

  const selectedSet = React.useMemo(() => new Set(value), [value])

  function toggle(optionValue: string) {
    const next = new Set(selectedSet)
    if (next.has(optionValue)) next.delete(optionValue)
    else next.add(optionValue)
    onValueChange(Array.from(next))
  }

  const summary = React.useMemo(() => {
    if (value.length === 0) return placeholder
    if (value.length <= maxLabels) {
      const labels = value.map((v) => options.find((o) => o.value === v)?.label ?? v)
      return labels.join(', ')
    }
    return `${value.length} selected`
  }, [value, options, placeholder, maxLabels])

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
          disabled={disabled}
          aria-label={summary}
          className={cn(
            'w-full justify-between font-normal',
            value.length === 0 && 'text-muted-foreground',
            className
          )}
        >
          <span className="truncate">{summary}</span>
          <ChevronDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder={searchPlaceholder} />
          <CommandList>
            <CommandEmpty>{emptyMessage}</CommandEmpty>
            <CommandGroup>
              {options.map((option) => {
                const isSelected = selectedSet.has(option.value)
                return (
                  <CommandItem
                    key={option.value}
                    value={option.value}
                    onSelect={() => toggle(option.value)}
                    role="option"
                    aria-selected={isSelected}
                  >
                    <div
                      className={cn(
                        'mr-2 flex h-4 w-4 items-center justify-center rounded-sm border',
                        isSelected
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-transparent'
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                    </div>
                    <span className="flex-1 truncate">{option.label}</span>
                    {isSelected && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          toggle(option.value)
                        }}
                        className="ml-2 rounded p-0.5 text-muted-foreground hover:text-foreground"
                        aria-label={`Remove ${option.label}`}
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                  </CommandItem>
                )
              })}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  )
}
