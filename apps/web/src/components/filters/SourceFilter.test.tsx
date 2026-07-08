import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { SourceFilter } from '@/components/filters/SourceFilter'
import { IntlWrapper } from '@/test-utils/intl-helper'

const replaceSpy = vi.fn()
let mockSearch = ''

vi.mock('@/i18n/navigation', () => ({
  useRouter: () => ({ replace: replaceSpy }),
  usePathname: () => '/search',
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

const SOURCES = ['techcrunch.com', 'theverge.com', 'arstechnica.com']

function renderFilter() {
  return render(
    <IntlWrapper>
      <SourceFilter options={SOURCES} />
    </IntlWrapper>
  )
}

function lastUrl(): string {
  const calls = replaceSpy.mock.calls
  return calls[calls.length - 1][0]
}

describe('SourceFilter', () => {
  beforeEach(() => {
    replaceSpy.mockReset()
    mockSearch = ''
  })

  it('renders the placeholder when nothing is selected', () => {
    renderFilter()
    expect(screen.getByRole('combobox')).toHaveTextContent('All sources')
  })

  it('renders the current value when ?source= is set', () => {
    mockSearch = '?source=theverge.com'
    renderFilter()
    expect(screen.getByRole('combobox')).toHaveTextContent('theverge.com')
  })

  it('opens the popover and shows all options', () => {
    renderFilter()
    fireEvent.click(screen.getByRole('combobox'))
    for (const s of SOURCES) {
      expect(screen.getByRole('option', { name: s })).toBeInTheDocument()
    }
  })

  it('selecting an option writes ?source= and closes the popover', () => {
    renderFilter()
    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.click(screen.getByRole('option', { name: 'techcrunch.com' }))
    const url = lastUrl()
    expect(url).toContain('source=techcrunch.com')
    expect(screen.queryByRole('option', { name: 'techcrunch.com' })).not.toBeInTheDocument()
  })

  it('clicking the clear (X) button removes the ?source= key', () => {
    mockSearch = '?source=theverge.com'
    renderFilter()
    fireEvent.click(screen.getByRole('button', { name: /clear source filter/i }))
    const url = lastUrl()
    expect(url).not.toContain('source=')
  })
})
