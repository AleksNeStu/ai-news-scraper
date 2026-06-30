import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ScoreRing } from '@/components/ScoreRing'

describe('ScoreRing', () => {
  it('renders an empty arc when score is null', () => {
    render(<ScoreRing score={null} />)
    const ring = screen.getByRole('img', { name: /Not yet scored/i })
    expect(ring).toBeInTheDocument()
    // The dim track circle plus the hidden arc both render; we just verify
    // the wrapper svg carries the null-score aria-label so a11y is exposed.
  })

  it('renders a 360° arc when score=1 (dashOffset === 0)', () => {
    render(<ScoreRing score={1} />)
    const ring = screen.getByRole('img')
    const arc = ring.querySelector('circle:nth-of-type(2)') as SVGCircleElement | null
    expect(arc).toBeTruthy()
    expect(arc?.getAttribute('stroke-dashoffset')).toBe('0')
  })

  it('renders a 0° arc when score=0 (dashOffset equals circumference)', () => {
    render(<ScoreRing score={0} />)
    const ring = screen.getByRole('img')
    const arc = ring.querySelector('circle:nth-of-type(2)') as SVGCircleElement | null
    expect(arc).toBeTruthy()
    // circumference ≈ 2π(12-1) = ~69.115 for sm; dashOffset === 2πr when score=0
    const dashOffset = Number(arc?.getAttribute('stroke-dashoffset'))
    const dashArray = Number(arc?.getAttribute('stroke-dasharray'))
    expect(dashOffset).toBeCloseTo(dashArray, 5)
  })

  it('aria-label reflects score and tier', () => {
    render(<ScoreRing score={0.85} tier="must_read" />)
    expect(
      screen.getByRole('img', { name: /Score 85 percent, tier must_read/i })
    ).toBeInTheDocument()
  })

  it("aria-label falls back to 'unknown' tier when tier is omitted", () => {
    render(<ScoreRing score={0.42} />)
    expect(screen.getByRole('img', { name: /Score 42 percent, tier unknown/i })).toBeInTheDocument()
  })

  it("renders the numeric label only when size='md' and showLabel=true", () => {
    const { rerender } = render(<ScoreRing score={0.75} showLabel />)
    expect(screen.queryByText('0.75')).not.toBeInTheDocument()

    rerender(<ScoreRing score={0.75} size="md" showLabel />)
    expect(screen.getByText('0.75')).toBeInTheDocument()
  })

  it('does not render the label when score is null', () => {
    render(<ScoreRing score={null} size="md" showLabel />)
    expect(screen.queryByText('0.00')).not.toBeInTheDocument()
  })
})
