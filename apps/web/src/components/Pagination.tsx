'use client'

/**
 * Pagination — stateless page navigation widget.
 *
 * URL contract is not owned here. The parent owns it: pass the
 * current `page`, the derived `totalPages`, and a stable
 * `onPageChange(n)` that updates the URL (typically via
 * `useFilterUrl().set('page', String(n))`).
 *
 * Renders First / Prev / 1 / … / current window / … / N / Next /
 * Last buttons inside a `<nav aria-label="Pagination">`. The
 * active page carries `aria-current="page"`. Buttons that would
 * navigate to the current page are disabled.
 *
 * Window rule: when totalPages > 7, the central window is
 * current-2..current+2 with the rest collapsed to "…" (with one
 * adjacent numeral anchor on each side). Smaller total is
 * rendered as a flat list 1..N.
 */

import * as React from 'react'
import { ChevronFirst, ChevronLast, ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'

export interface PaginationProps {
  /** Current 1-indexed page. */
  page: number
  /** Total number of pages (>= 1). */
  totalPages: number
  /** Called with the next 1-indexed page. */
  onPageChange: (next: number) => void
  className?: string
  /** Localization for the visible labels (default: English). */
  labels?: {
    first?: string
    prev?: string
    next?: string
    last?: string
    page?: (n: number) => string
  }
}

const DEFAULT_LABELS = {
  first: 'First page',
  prev: 'Previous page',
  next: 'Next page',
  last: 'Last page',
  page: (n: number) => `Page ${n}`,
} as const

function buildPages(current: number, total: number): Array<number | 'gap'> {
  // Compact window: 1 … [c-1 c c+1] … N when total > 7.
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1)
  }
  const pages: Array<number | 'gap'> = [1]
  const start = Math.max(2, current - 1)
  const end = Math.min(total - 1, current + 1)
  if (start > 2) pages.push('gap')
  for (let p = start; p <= end; p++) pages.push(p)
  if (end < total - 1) pages.push('gap')
  pages.push(total)
  return pages
}

export function Pagination({ page, totalPages, onPageChange, className, labels }: PaginationProps) {
  if (totalPages < 1) return null
  const safePage = Math.min(Math.max(1, page), totalPages)
  const L = { ...DEFAULT_LABELS, ...labels }
  const items = buildPages(safePage, totalPages)
  const canPrev = safePage > 1
  const canNext = safePage < totalPages

  function go(n: number) {
    const target = Math.min(Math.max(1, n), totalPages)
    if (target !== safePage) onPageChange(target)
  }

  return (
    <nav
      aria-label="Pagination"
      className={cn('flex items-center justify-center gap-1', className)}
    >
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => go(1)}
        disabled={!canPrev}
        aria-label={L.first}
      >
        <ChevronFirst className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => go(safePage - 1)}
        disabled={!canPrev}
        aria-label={L.prev}
      >
        <ChevronLeft className="h-4 w-4" />
      </Button>
      <ul className="flex items-center gap-1">
        {items.map((item, idx) =>
          item === 'gap' ? (
            <li
              key={`gap-${idx}`}
              aria-hidden="true"
              className="inline-flex h-9 w-9 items-center justify-center text-muted-foreground"
            >
              <MoreHorizontal className="h-4 w-4" />
            </li>
          ) : (
            <li key={item}>
              <Button
                type="button"
                variant={item === safePage ? 'default' : 'outline'}
                size="icon"
                onClick={() => go(item)}
                aria-current={item === safePage ? 'page' : undefined}
                aria-label={item === safePage ? L.page(item) : `Go to page ${item}`}
                className="tabular-nums"
              >
                {item}
              </Button>
            </li>
          )
        )}
      </ul>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => go(safePage + 1)}
        disabled={!canNext}
        aria-label={L.next}
      >
        <ChevronRight className="h-4 w-4" />
      </Button>
      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={() => go(totalPages)}
        disabled={!canNext}
        aria-label={L.last}
      >
        <ChevronLast className="h-4 w-4" />
      </Button>
    </nav>
  )
}
