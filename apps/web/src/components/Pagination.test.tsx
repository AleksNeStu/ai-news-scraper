import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Pagination } from '@/components/Pagination'

const onPageChange = vi.fn()

describe('Pagination', () => {
  beforeEach(() => onPageChange.mockReset())

  it('renders nothing when totalPages < 1', () => {
    const { container } = render(<Pagination page={1} totalPages={0} onPageChange={onPageChange} />)
    expect(container.firstChild).toBeNull()
  })

  it('shows all pages when totalPages <= 7', () => {
    render(<Pagination page={1} totalPages={5} onPageChange={onPageChange} />)
    for (let i = 1; i <= 5; i++) {
      expect(
        screen.getByRole('button', { name: i === 1 ? /^Page 1$/ : new RegExp(`^Go to page ${i}$`) })
      ).toBeInTheDocument()
    }
  })

  it('marks the current page with aria-current=page', () => {
    render(<Pagination page={3} totalPages={5} onPageChange={onPageChange} />)
    expect(screen.getByRole('button', { name: /^Page 3$/ })).toHaveAttribute('aria-current', 'page')
  })

  it('renders the compact window with … for totalPages > 7', () => {
    render(<Pagination page={10} totalPages={20} onPageChange={onPageChange} />)
    // should show: 1 … 9 10 11 … 20
    expect(screen.queryByRole('button', { name: /^Go to page 8$/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Go to page 9$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Page 10$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Go to page 11$/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^Go to page 12$/ })).not.toBeInTheDocument()
    // Ellipsis indicators exist (gap li nodes carry aria-hidden="true").
    expect(
      document.querySelectorAll('nav[aria-label="Pagination"] [aria-hidden="true"]').length
    ).toBeGreaterThan(0)
  })

  it('disables First/Prev on page=1 and Next/Last on the last page', () => {
    const { rerender } = render(<Pagination page={1} totalPages={10} onPageChange={onPageChange} />)
    expect(screen.getByRole('button', { name: /first page/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /previous page/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /next page/i })).not.toBeDisabled()
    expect(screen.getByRole('button', { name: /last page/i })).not.toBeDisabled()

    rerender(<Pagination page={10} totalPages={10} onPageChange={onPageChange} />)
    expect(screen.getByRole('button', { name: /next page/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /last page/i })).toBeDisabled()
  })

  it('clicking a page number calls onPageChange with that page', () => {
    render(<Pagination page={1} totalPages={5} onPageChange={onPageChange} />)
    fireEvent.click(screen.getByRole('button', { name: /^Go to page 3$/ }))
    expect(onPageChange).toHaveBeenCalledWith(3)
  })

  it('clicking Next moves to page+1; Last to totalPages', () => {
    render(<Pagination page={3} totalPages={10} onPageChange={onPageChange} />)
    fireEvent.click(screen.getByRole('button', { name: /next page/i }))
    expect(onPageChange).toHaveBeenLastCalledWith(4)
    fireEvent.click(screen.getByRole('button', { name: /last page/i }))
    expect(onPageChange).toHaveBeenLastCalledWith(10)
  })

  it('clamps page <= totalPages when the parent over-runs', () => {
    render(<Pagination page={99} totalPages={5} onPageChange={onPageChange} />)
    // Active button should still be present (we clamp internally)
    expect(screen.getByRole('button', { name: /Page 5/i })).toHaveAttribute('aria-current', 'page')
    // Next/Last are disabled because we're already at the end
    expect(screen.getByRole('button', { name: /next page/i })).toBeDisabled()
  })
})
