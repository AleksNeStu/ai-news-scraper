import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ArticlesToolbar } from '@/app/(app)/articles/ArticlesToolbar'

const replaceSpy = vi.fn()
let mockSearch = ''

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceSpy }),
  usePathname: () => '/articles',
  useSearchParams: () => new URLSearchParams(mockSearch),
}))

describe('ArticlesToolbar', () => {
  beforeEach(() => {
    replaceSpy.mockReset()
    mockSearch = ''
  })

  it('sets ?tier=<tier> when a chip is clicked', () => {
    render(<ArticlesToolbar activeTier={null} grouped={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Must Read' }))
    expect(replaceSpy).toHaveBeenCalled()
    const url = String(replaceSpy.mock.calls[0]?.[0] ?? '')
    expect(url).toContain('tier=must_read')
  })

  it('clears ?tier when the All chip is clicked', () => {
    render(<ArticlesToolbar activeTier="must_read" grouped={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(replaceSpy).toHaveBeenCalled()
    const url = String(replaceSpy.mock.calls[0]?.[0] ?? '')
    expect(url).not.toContain('tier=')
  })

  it('marks the active chip with aria-pressed=true', () => {
    render(<ArticlesToolbar activeTier="recommended" grouped={false} />)
    expect(screen.getByRole('button', { name: 'Recommended' })).toHaveAttribute(
      'aria-pressed',
      'true'
    )
    expect(screen.getByRole('button', { name: 'All' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('hides the chip row and surfaces the toggle when grouped is true', () => {
    render(<ArticlesToolbar activeTier={null} grouped={true} />)
    expect(screen.queryByRole('group', { name: /Filter by tier/i })).not.toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: /Group by tier/i })).toBeChecked()
  })

  it('toggles group_by_tier on checkbox change', () => {
    render(<ArticlesToolbar activeTier={null} grouped={false} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /Group by tier/i }))
    expect(replaceSpy).toHaveBeenCalled()
    const url = String(replaceSpy.mock.calls[0]?.[0] ?? '')
    expect(url).toContain('group_by_tier=true')
  })

  it('clears group_by_tier when toggling off', () => {
    render(<ArticlesToolbar activeTier={null} grouped={true} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /Group by tier/i }))
    const url = String(replaceSpy.mock.calls[0]?.[0] ?? '')
    expect(url).not.toContain('group_by_tier=')
  })

  // Devil M#1, Task #9 review: filter/view changes must reset ?page.
  it('resets ?page when a tier chip is clicked while on page 2+', () => {
    mockSearch = 'page=2'
    render(<ArticlesToolbar activeTier={null} grouped={false} />)
    fireEvent.click(screen.getByRole('button', { name: 'Must Read' }))
    const url = String(replaceSpy.mock.calls[0]?.[0] ?? '')
    expect(url).toContain('tier=must_read')
    expect(url).not.toContain('page=2')
  })

  it('resets ?page when toggling group_by_tier', () => {
    mockSearch = 'page=3'
    render(<ArticlesToolbar activeTier={null} grouped={false} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /Group by tier/i }))
    const url = String(replaceSpy.mock.calls[0]?.[0] ?? '')
    expect(url).toContain('group_by_tier=true')
    expect(url).not.toContain('page=3')
  })
})
