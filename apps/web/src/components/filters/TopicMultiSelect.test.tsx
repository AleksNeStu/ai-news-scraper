import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TopicMultiSelect } from '@/components/filters/TopicMultiSelect'
import { IntlWrapper } from '@/test-utils/intl-helper'
import type { MultiSelectOption } from '@/components/ui/multi-select'

const replaceSpy = vi.fn()
let mockSearch = ''

vi.mock('@/i18n/navigation', () => ({
  useRouter: () => ({ replace: replaceSpy }),
  usePathname: () => '/search',
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

const TOPICS: MultiSelectOption[] = [
  { value: 'ai', label: 'AI' },
  { value: 'rag', label: 'RAG' },
  { value: 'ml', label: 'ML' },
]

function renderSelect() {
  return render(
    <IntlWrapper>
      <TopicMultiSelect options={TOPICS} />
    </IntlWrapper>
  )
}

function lastUrl(): string {
  const calls = replaceSpy.mock.calls
  return calls[calls.length - 1][0]
}

describe('TopicMultiSelect', () => {
  beforeEach(() => {
    replaceSpy.mockReset()
    mockSearch = ''
  })

  it('renders the placeholder when nothing is selected', () => {
    renderSelect()
    expect(screen.getByRole('combobox')).toHaveTextContent('All topics')
  })

  it('reading two ?topic= values shows both labels in the trigger', () => {
    mockSearch = '?topic=ai&topic=rag'
    renderSelect()
    const cb = screen.getByRole('combobox')
    expect(cb).toHaveTextContent('AI')
    expect(cb).toHaveTextContent('RAG')
  })

  it('selecting an option appends ?topic=', () => {
    renderSelect()
    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.click(screen.getByRole('option', { name: 'AI' }))
    expect(lastUrl()).toContain('topic=ai')
  })

  it('selecting a second option keeps the first and adds the second', () => {
    mockSearch = '?topic=ai'
    renderSelect()
    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.click(screen.getByRole('option', { name: 'RAG' }))
    const url = lastUrl()
    expect(url).toContain('topic=ai')
    expect(url).toContain('topic=rag')
  })

  it('clicking the X on a selected item removes only that one', () => {
    mockSearch = '?topic=ai&topic=rag'
    renderSelect()
    fireEvent.click(screen.getByRole('combobox'))
    fireEvent.click(screen.getByRole('button', { name: 'Remove AI' }))
    const url = lastUrl()
    expect(url).not.toContain('topic=ai')
    expect(url).toContain('topic=rag')
  })
})
