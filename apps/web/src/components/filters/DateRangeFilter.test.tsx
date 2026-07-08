import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { DateRangeFilter } from '@/components/filters/DateRangeFilter'
import { IntlWrapper } from '@/test-utils/intl-helper'

const replaceSpy = vi.fn()
let mockSearch = ''

vi.mock('@/i18n/navigation', () => ({
  useRouter: () => ({ replace: replaceSpy }),
  usePathname: () => '/search',
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

function renderFilter() {
  return render(
    <IntlWrapper>
      <DateRangeFilter />
    </IntlWrapper>
  )
}

function lastUrl(): string {
  const calls = replaceSpy.mock.calls
  return calls[calls.length - 1][0]
}

describe('DateRangeFilter', () => {
  beforeEach(() => {
    replaceSpy.mockReset()
    mockSearch = ''
  })

  it('renders the "Any date" placeholder when nothing is set', () => {
    renderFilter()
    expect(screen.getByRole('button')).toHaveTextContent('Any date')
  })

  it('renders the current range when ?from= and ?to= are set', () => {
    mockSearch = '?from=2026-01-01&to=2026-12-31'
    renderFilter()
    expect(screen.getByRole('button', { name: /2026-01-01/ })).toBeInTheDocument()
  })

  it('opening the popover reveals both date inputs', () => {
    renderFilter()
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByLabelText(/from/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/to/i)).toBeInTheDocument()
  })

  it('setting ?from= writes the from key and drops ?page', () => {
    mockSearch = '?q=ai&page=2'
    renderFilter()
    fireEvent.click(screen.getByRole('button'))
    fireEvent.change(screen.getByLabelText(/from/i), { target: { value: '2026-01-01' } })
    const url = lastUrl()
    expect(url).toContain('from=2026-01-01')
    expect(url).not.toContain('page=')
    expect(url).toContain('q=ai')
  })

  it('clicking the clear (X) removes both keys', () => {
    mockSearch = '?from=2026-01-01&to=2026-12-31'
    renderFilter()
    fireEvent.click(screen.getByRole('button', { name: /clear date range/i }))
    const url = lastUrl()
    expect(url).not.toContain('from=')
    expect(url).not.toContain('to=')
  })

  it('the "to" input has min=from so the picker refuses earlier dates', () => {
    mockSearch = '?from=2026-06-01'
    renderFilter()
    fireEvent.click(screen.getByRole('button', { name: /2026-06-01/ }))
    const to = screen.getByLabelText(/to/i) as HTMLInputElement
    expect(to.min).toBe('2026-06-01')
  })
})
