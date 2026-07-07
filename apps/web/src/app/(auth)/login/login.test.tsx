import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, act, waitFor } from '@testing-library/react'
import LoginPage from '@/app/(auth)/login/page'
import * as authMod from '@/lib/auth'
import type { LoginState } from '@/lib/auth'

// The login page is a `'use client'` component that drives its UI off the
// `useActionState` hook. In jsdom the React 19 server-action plumbing
// (`<form action={action}>`) doesn't round-trip — the form's `action`
// attribute is rendered as a `javascript:throw new Error(...)` placeholder
// that React's document-level submit delegate would intercept in a real
// browser but not in jsdom. To keep this test focused on the cooldown UX
// (the part we own), we mock `useActionState` to return a controllable
// `(state, action, pending)` tuple per scenario. The server-action
// integration is covered by backend tests on ADR-015 §15.10.

const useActionStateMock = vi.fn()

import type * as ReactModule from 'react'

vi.mock('react', async (importOriginal) => {
  const actual = (await importOriginal()) as typeof ReactModule
  return {
    ...actual,
    useActionState: (action: unknown, initial: unknown) => useActionStateMock(action, initial),
  }
})

beforeEach(() => {
  vi.restoreAllMocks()
  // Default mock: pending=false, state=initial. Tests override per-case.
  useActionStateMock.mockImplementation((_action, initial) => [initial, vi.fn(), false])
  // jsdom lacks window.location.assign — stub the redirect side-effect.
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, href: '' },
    writable: true,
  })
})

afterEach(() => {
  vi.useRealTimers()
})

function setState(state: LoginState, pending = false) {
  useActionStateMock.mockImplementation(() => [state, vi.fn(), pending])
}

describe('LoginPage — rate-limit cooldown UX (ADR-015 H2)', () => {
  it('renders the 429 message with a countdown when the server returns Retry-After', async () => {
    setState({
      ok: false,
      code: 'rate_limited',
      retryAfter: 30,
      error: 'Too many attempts. Try again in 30 seconds.',
    })

    render(<LoginPage />)

    expect(screen.getByText(/Too many attempts\. Try again in 30 seconds\./i)).toBeInTheDocument()
    // Submit button reflects the countdown.
    expect(screen.getByRole('button', { name: /Retry in 30s/i })).toBeDisabled()
    // aria-live region announces the seconds remaining.
    expect(screen.getByText(/Retrying in 30s/i)).toBeInTheDocument()
  })

  it('decrements the cooldown every second and re-enables submit at 0', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    setState({
      ok: false,
      code: 'rate_limited',
      retryAfter: 3,
      error: 'Too many attempts. Try again in 3 seconds.',
    })

    render(<LoginPage />)
    expect(screen.getByRole('button', { name: /Retry in 3s/i })).toBeDisabled()

    // Tick 2s.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000)
    })
    expect(screen.getByRole('button', { name: /Retry in 1s/i })).toBeDisabled()

    // One more tick → cooldown at 0 → submit becomes available again.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000)
    })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled()
    })
    expect(screen.queryByText(/Retrying in/i)).not.toBeInTheDocument()
  })

  it('renders a generic error (without countdown) on a non-429 failure', async () => {
    setState({ ok: false, error: 'Invalid credentials' })

    render(<LoginPage />)

    expect(screen.getByText(/Invalid credentials/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled()
    expect(screen.queryByText(/Retry in/i)).not.toBeInTheDocument()
  })

  it('moves keyboard focus to the error message on render', async () => {
    setState({ ok: false, error: 'Invalid credentials' })

    render(<LoginPage />)
    const error = await screen.findByRole('alert')
    expect(error).toHaveTextContent(/Invalid credentials/i)
    await waitFor(() => expect(document.activeElement).toBe(error))
  })

  it('disables the email + password fields while in cooldown so the user cannot edit', () => {
    setState({
      ok: false,
      code: 'rate_limited',
      retryAfter: 30,
      error: 'Too many attempts. Try again in 30 seconds.',
    })

    render(<LoginPage />)
    const email = document.querySelector<HTMLInputElement>('input[name="email"]')
    const password = document.querySelector<HTMLInputElement>('input[name="password"]')
    expect(email).toBeDisabled()
    expect(password).toBeDisabled()
  })

  it('marks the submit button aria-busy while a submission is in-flight', () => {
    setState({ ok: false, error: 'Invalid credentials' }, true)

    render(<LoginPage />)
    const button = screen.getByRole('button', { name: /signing in/i })
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})

// Reference check: loginAction is still imported (the page wires its
// signature through useActionState at runtime). Asserting the import
// surface exists prevents an accidental tree-shake / typo.
describe('LoginPage — wiring', () => {
  it('imports loginAction from @/lib/auth', () => {
    expect(authMod.loginAction).toBeDefined()
  })
})
