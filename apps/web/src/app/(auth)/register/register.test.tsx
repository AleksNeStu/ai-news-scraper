import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import RegisterPage from '@/app/(auth)/register/page'
import type { RegisterState } from '@/lib/auth'

// The register page is a `'use client'` component that drives its UI off
// the `useActionState` hook. The same caveat as login.test.tsx applies:
// React 19's server-action plumbing doesn't round-trip in jsdom (the
// form's `action` attribute is a server-action placeholder), so we mock
// `useActionState` and drive the state tuple directly.
import type * as ReactModule from 'react'

const useActionStateMock = vi.fn()

vi.mock('react', async (importOriginal) => {
  const actual = (await importOriginal()) as typeof ReactModule
  return {
    ...actual,
    useActionState: (action: unknown, initial: unknown) => useActionStateMock(action, initial),
  }
})

beforeEach(() => {
  vi.restoreAllMocks()
  useActionStateMock.mockImplementation((_action, initial) => [initial, vi.fn(), false])
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, href: '' },
    writable: true,
  })
})

afterEach(() => {
  vi.useRealTimers()
})

function setState(state: RegisterState, pending = false) {
  useActionStateMock.mockImplementation(() => [state, vi.fn(), pending])
}

describe('RegisterPage — mass-assignment 422 surface (ADR-015 H1)', () => {
  it('renders per-field errors when the server rejects forbidden extras', async () => {
    setState({
      ok: false,
      code: 'validation_error',
      fieldErrors: {
        is_admin: 'Extra inputs are not permitted',
      },
    })

    render(<RegisterPage />)

    // The “bucket” error region (role=alert) renders the rejected field
    // name + Pydantic message. We render the field name in monospace so
    // users who tampered with the request can see exactly which key was
    // refused.
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/is_admin/)
    expect(alert).toHaveTextContent(/Extra inputs are not permitted/i)
  })

  it('renders email + password field errors inline next to their inputs', async () => {
    setState({
      ok: false,
      code: 'validation_error',
      fieldErrors: {
        email: 'value is not a valid email address',
        password: 'String should have at least 8 characters',
      },
    })

    render(<RegisterPage />)

    expect(screen.getByText(/value is not a valid email address/i)).toBeInTheDocument()
    expect(screen.getByText(/String should have at least 8 characters/i)).toBeInTheDocument()

    // Inputs are marked aria-invalid so screen-readers announce the
    // error context.
    const email = document.querySelector<HTMLInputElement>('input[name="email"]')
    const password = document.querySelector<HTMLInputElement>('input[name="password"]')
    expect(email?.getAttribute('aria-invalid')).toBe('true')
    expect(password?.getAttribute('aria-invalid')).toBe('true')
  })

  it('falls back to the generic error string on a non-422 failure', async () => {
    setState({ ok: false, error: 'Email already registered' })

    render(<RegisterPage />)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/Email already registered/i)
  })

  it('moves keyboard focus to the first error on render', async () => {
    setState({
      ok: false,
      code: 'validation_error',
      fieldErrors: { is_admin: 'Extra inputs are not permitted' },
    })

    render(<RegisterPage />)
    const error = await screen.findByRole('alert')
    expect(error).toHaveTextContent(/is_admin/i)
    await waitFor(() => expect(document.activeElement).toBe(error))
  })

  it('marks the submit button aria-busy while a submission is in flight', () => {
    setState({ ok: false, error: 'Email already registered' }, true)

    render(<RegisterPage />)
    const button = screen.getByRole('button', { name: /creating/i })
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})
