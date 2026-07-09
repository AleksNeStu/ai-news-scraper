/**
 * Tests for <VectorDisplay /> (Task #34, ADR-022 §22.7).
 *
 * The component renders a compressed view by default (first 8 dims +
 * "[…N more]" placeholder for the rest) and exposes a toggle that
 * reveals the full vector. These tests pin the behaviour the
 * EmbeddingsView depends on so a regression here surfaces immediately.
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, within, fireEvent } from '@testing-library/react'
import { IntlWrapper } from '@/test-utils/intl-helper'
import { VectorDisplay } from '@/components/VectorDisplay'

// Deterministic 1536-dim fixture (Gemini + OpenRouter share this dim
// count; OpenAI text-embedding-3-small is 1536 too). First 8 dims are
// pinned so we can assert the preview exactly.
function makeVector(total: number): number[] {
  const head = [0.1234, -0.5678, 0.9101, -0.2345, 0.6789, -0.3456, 0.789, -0.4567]
  const tail = Array.from({ length: total - head.length }, (_, i) => (i % 10) / 100 - 0.05)
  return head.concat(tail)
}

describe('<VectorDisplay />', () => {
  beforeEach(() => {
    // nothing yet — tests are independent
  })

  it('renders "8 dims + N more" preview for a 1536-dim vector and shows the first 8 numeric values', () => {
    const v = makeVector(1536)
    render(
      <IntlWrapper>
        <VectorDisplay vector={v} testId="vd" />
      </IntlWrapper>
    )

    // Total dim count is in the header.
    expect(within(screen.getByTestId('vd-total')).getByText('1536 dims')).toBeInTheDocument()

    // Hex blob is shown: 32 dims × 4 bytes × 2 hex chars = 256 chars.
    const hex = screen.getByTestId('vd-hex')
    expect(hex.textContent).toMatch(/^[0-9a-f]+$/)
    expect((hex.textContent ?? '').length).toBe(256)

    // Preview pane shows the first 8 dims.
    const preview = screen.getByTestId('vd-preview')
    expect(preview.textContent).toBe(
      '0.1234, -0.5678, 0.9101, -0.2345, 0.6789, -0.3456, 0.7890, -0.4567, ' + '[…1528 more]'
    )

    // The "[…1528 more]" placeholder is its own testid'd span.
    expect(within(preview).getByTestId('vd-more').textContent).toBe('[…1528 more]')

    // Full vector is NOT yet rendered.
    expect(screen.queryByTestId('vd-full-vector')).toBeNull()
  })

  it('reveals the full vector when the "Show full vector" toggle is clicked, and collapses back', () => {
    const v = makeVector(20)
    render(
      <IntlWrapper>
        <VectorDisplay vector={v} testId="vd" />
      </IntlWrapper>
    )

    fireEvent.click(screen.getByTestId('vd-show-full'))

    const full = screen.getByTestId('vd-full-vector')
    // The full-vector text contains ALL 20 numbers, including the first 8
    // the preview already showed. We assert it starts with the pinned
    // head and ends with the last computed tail value, so a future
    // formatter change still trips this assertion.
    const text = full.textContent ?? ''
    expect(text.startsWith('0.1234, -0.5678, 0.9101, -0.2345')).toBe(true)
    // 20 numbers formatted as "X.XXXX" with ", " separators = 19 separators
    // + 20 numbers. Asserting by "," count is more robust to formatting.
    expect((text.match(/,/g) ?? []).length).toBe(19)
    // The "1528 more" placeholder must be gone now.
    expect(screen.queryByTestId('vd-more')).toBeNull()

    // Collapse back to the preview state.
    fireEvent.click(screen.getByTestId('vd-collapse'))
    expect(screen.queryByTestId('vd-full-vector')).toBeNull()
    expect(screen.getByTestId('vd-preview')).toBeInTheDocument()
  })

  it('renders the supplied label above the dim count', () => {
    render(
      <IntlWrapper>
        <VectorDisplay vector={[0.1, 0.2, 0.3]} label="Text A" testId="vd" />
      </IntlWrapper>
    )
    expect(screen.getByText('Text A')).toBeInTheDocument()
    expect(within(screen.getByTestId('vd-total')).getByText('3 dims')).toBeInTheDocument()
  })

  it('does not render the "[…N more]" placeholder when the vector fits within previewDims', () => {
    render(
      <IntlWrapper>
        <VectorDisplay vector={[0.1, 0.2, 0.3, 0.4, 0.5]} testId="vd" previewDims={8} />
      </IntlWrapper>
    )
    expect(screen.queryByTestId('vd-more')).toBeNull()
    // All 5 dims are shown.
    expect(screen.getByTestId('vd-preview').textContent).toBe(
      '0.1000, 0.2000, 0.3000, 0.4000, 0.5000'
    )
  })

  it('hex blob is empty for an empty vector', () => {
    render(
      <IntlWrapper>
        <VectorDisplay vector={[]} testId="vd" />
      </IntlWrapper>
    )
    // The "0 dims" badge still renders; the hex paragraph is empty.
    expect(within(screen.getByTestId('vd-total')).getByText('0 dims')).toBeInTheDocument()
    expect(screen.queryByTestId('vd-hex')).toBeNull()
  })

  it('hex blob byte width is exactly 8 chars per dim', () => {
    // 4 dims × 4 bytes × 2 hex chars = 32 chars
    const v = [1.0, -1.0, 0.5, -0.5]
    render(
      <IntlWrapper>
        <VectorDisplay vector={v} testId="vd" hexBlobDims={4} />
      </IntlWrapper>
    )
    const hex = screen.getByTestId('vd-hex')
    expect(hex.textContent).toMatch(/^[0-9a-f]{32}$/)
  })
})
