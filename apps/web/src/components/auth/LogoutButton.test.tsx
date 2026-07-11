import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { LogoutButton } from '@/components/auth/LogoutButton'
import { IntlWrapper } from '@/test-utils/intl-helper'
import * as authMod from '@/lib/auth'

// Stub the server action. In jsdom we don't round-trip the React 19
// server-action plumbing; we drive the component's transition state
// directly.
const logoutMock = vi.fn()

beforeEach(() => {
  vi.restoreAllMocks()
  vi.spyOn(authMod, 'logoutAction').mockImplementation(logoutMock)
})

afterEach(() => {
  vi.useRealTimers()
})

function renderLogout() {
  return render(
    <IntlWrapper>
      <LogoutButton />
    </IntlWrapper>
  )
}

describe('LogoutButton — server-confirmed logout (ADR-015 H3)', () => {
  it('renders the logout button as enabled with the default label', () => {
    renderLogout()
    const button = screen.getByRole('button', { name: /logout/i })
    expect(button).toBeInTheDocument()
    expect(button).not.toBeDisabled()
    expect(button).not.toHaveAttribute('aria-busy', 'true')
  })

  it('marks the button aria-busy and shows "Logging out…" while the action is in flight', async () => {
    // Hang the action so we can observe the pending state.
    logoutMock.mockImplementation(
      () => new Promise(() => {}) // never resolves
    )

    renderLogout()
    const button = screen.getByRole('button', { name: /logout/i })
    fireEvent.click(button)

    await waitFor(() => {
      const pendingButton = screen.getByRole('button', { name: /logging out/i })
      expect(pendingButton).toBeDisabled()
      expect(pendingButton).toHaveAttribute('aria-busy', 'true')
    })
  })

  it('does not leave focus on the disabled pending button after click', async () => {
    // Hang the action so we can observe the pending state.
    logoutMock.mockImplementation(
      () => new Promise(() => {}) // never resolves
    )

    renderLogout()
    const button = screen.getByRole('button', { name: /logout/i })
    button.focus()
    expect(document.activeElement).toBe(button)

    fireEvent.click(button)

    await waitFor(() => {
      const pendingButton = screen.getByRole('button', { name: /logging out/i })
      expect(pendingButton).toBeDisabled()
      expect(document.activeElement).not.toBe(pendingButton)
    })
  })

  it('surfaces the server-error result inline and re-enables the button', async () => {
    logoutMock.mockResolvedValue({
      ok: false,
      error: 'Logout failed. Please try again.',
    })

    renderLogout()
    fireEvent.click(screen.getByRole('button', { name: /logout/i }))

    // Action returned; component should now show the error + re-enabled button.
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/logout failed/i)

    // Button is enabled again — user can retry.
    const button = screen.getByRole('button', { name: /logout/i })
    await waitFor(() => expect(button).not.toBeDisabled())
  })

  it('handles a thrown server action (transport failure) the same as a server-error result', async () => {
    logoutMock.mockRejectedValue(new Error('network'))

    renderLogout()
    fireEvent.click(screen.getByRole('button', { name: /logout/i }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/logout failed/i)
  })

  it('clears a prior error when the user clicks again after a failure', async () => {
    logoutMock.mockResolvedValueOnce({
      ok: false,
      error: 'Logout failed. Please try again.',
    })
    logoutMock.mockResolvedValueOnce(
      new Promise(() => {}) // second click hangs the action
    )

    renderLogout()

    // First click — error shown.
    fireEvent.click(screen.getByRole('button', { name: /logout/i }))
    await screen.findByRole('alert')

    // Second click — error should clear at the start of the new attempt.
    fireEvent.click(screen.getByRole('button', { name: /logout/i }))
    await waitFor(() => {
      // alert disappears during the in-flight second click
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })
})
