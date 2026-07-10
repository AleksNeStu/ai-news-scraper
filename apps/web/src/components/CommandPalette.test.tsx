import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

import { CommandPalette } from '@/components/CommandPalette'
import { IntlWrapper } from '@/test-utils/intl-helper'

// Mock the i18n router so we can assert the submitted URL without a
// real next-intl routing context. `push` resolves a promise so the
// component's call site (`router.push(...)`) doesn't blow up.
const pushSpy = vi.fn()
const replaceSpy = vi.fn()

vi.mock('@/i18n/navigation', async () => {
  const actual = await vi.importActual<typeof import('@/i18n/navigation')>('@/i18n/navigation')
  return {
    ...actual,
    useRouter: () => ({ push: pushSpy, replace: replaceSpy }),
  }
})

function renderPalette() {
  return render(
    <IntlWrapper>
      <CommandPalette />
    </IntlWrapper>
  )
}

function fireCmdK(opts: { metaKey?: boolean; ctrlKey?: boolean } = {}) {
  fireEvent.keyDown(document, {
    key: 'k',
    code: 'KeyK',
    metaKey: opts.metaKey ?? false,
    ctrlKey: opts.ctrlKey ?? false,
  })
}

describe('CommandPalette', () => {
  beforeEach(() => {
    pushSpy.mockReset()
    replaceSpy.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('renders a trigger button with aria-keyshortcuts and a localized label', () => {
    renderPalette()
    const btn = screen.getByTestId('command-palette-trigger')
    expect(btn).toBeInTheDocument()
    expect(btn).toHaveAttribute('aria-label', 'Open search')
    expect(btn).toHaveAttribute('aria-keyshortcuts', 'Meta+K Control+K')
    // Dialog is closed initially.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens on Cmd+K (metaKey) and closes on the same combo', async () => {
    renderPalette()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    fireCmdK({ metaKey: true })
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    fireCmdK({ metaKey: true })
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('opens on Ctrl+K (ctrlKey)', async () => {
    renderPalette()
    fireCmdK({ ctrlKey: true })
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })

  it('does not open when K is pressed without a modifier', () => {
    renderPalette()
    fireEvent.keyDown(document, { key: 'k', code: 'KeyK' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('does not toggle when the user is typing in another input on the page', () => {
    // Mount a sibling input to confirm the listener ignores it.
    render(
      <IntlWrapper>
        <input data-testid="outside-input" />
        <CommandPalette />
      </IntlWrapper>
    )
    const outside = screen.getByTestId('outside-input')
    fireEvent.keyDown(outside, { key: 'k', code: 'KeyK', metaKey: true })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('shows the empty hint and a search input when open', async () => {
    renderPalette()
    fireCmdK({ metaKey: true })
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
    expect(screen.getByTestId('command-palette-input')).toBeInTheDocument()
    expect(screen.getByText('Type to search articles')).toBeInTheDocument()
  })

  it('navigates to /search?q=<query> on Enter with a non-empty query', async () => {
    renderPalette()
    fireCmdK({ metaKey: true })
    const input = await screen.findByTestId('command-palette-input')
    fireEvent.change(input, { target: { value: 'embeddings' } })
    fireEvent.submit(input.closest('form') as HTMLFormElement)
    expect(pushSpy).toHaveBeenCalledTimes(1)
    expect(pushSpy).toHaveBeenCalledWith({
      pathname: '/search',
      query: { q: 'embeddings' },
    })
    // Dialog closes on submit.
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('does not navigate on Enter when the query is empty or whitespace-only', async () => {
    renderPalette()
    fireCmdK({ metaKey: true })
    const input = await screen.findByTestId('command-palette-input')
    // Empty
    fireEvent.submit(input.closest('form') as HTMLFormElement)
    expect(pushSpy).not.toHaveBeenCalled()
    // Whitespace only
    fireEvent.change(input, { target: { value: '   ' } })
    fireEvent.submit(input.closest('form') as HTMLFormElement)
    expect(pushSpy).not.toHaveBeenCalled()
    // Dialog stays open on empty submit (so the user can refine the query).
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('opens via the visible trigger button (click) without a keyboard combo', async () => {
    renderPalette()
    fireEvent.click(screen.getByTestId('command-palette-trigger'))
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })

  it('resets the query between opens so a stale value does not stick', async () => {
    renderPalette()
    fireCmdK({ metaKey: true })
    let input = await screen.findByTestId('command-palette-input')
    fireEvent.change(input, { target: { value: 'first query' } })
    // Close via Cmd+K
    fireCmdK({ metaKey: true })
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
    // Re-open and confirm the input is empty.
    fireCmdK({ metaKey: true })
    input = await screen.findByTestId('command-palette-input')
    expect(input).toHaveValue('')
  })
})
