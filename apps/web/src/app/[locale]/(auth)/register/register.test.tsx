import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import RegisterPage from '@/app/[locale]/(auth)/register/page'
import { IntlWrapper } from '@/test-utils/intl-helper'
import { registerAction } from '@/lib/auth'
import type { RegisterState } from '@/lib/auth'
import type * as NextIntlModule from 'next-intl'

// The register page is a `'use client'` component that drives its UI off
// the `useActionState` hook. The same caveat as login.test.tsx applies:
// React 19's server-action plumbing doesn't round-trip in jsdom (the
// form's `action` attribute is a server-action placeholder), so we mock
// `useActionState` and drive the state tuple directly.
import type * as ReactModule from 'react'

const useActionStateMock = vi.fn()
let capturedRegisterAction:
  ((prev: RegisterState, formData: FormData) => Promise<RegisterState>) | null = null

// useLocale() stub — the register page passes the active locale into
// registerAction. 'en' keeps messages/en.json as the catalog inside
// IntlWrapper so the existing English assertions still hold.
vi.mock('next-intl', async (importOriginal) => {
  const actual = (await importOriginal()) as typeof NextIntlModule
  return {
    ...actual,
    useLocale: () => 'en',
  }
})

vi.mock('react', async (importOriginal) => {
  const actual = (await importOriginal()) as typeof ReactModule
  return {
    ...actual,
    useActionState: (action: unknown, initial: unknown) => useActionStateMock(action, initial),
  }
})

vi.mock('@/i18n/navigation', () => ({
  Link: ({
    href,
    children,
    className,
  }: {
    href: string
    children: React.ReactNode
    className?: string
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}))

vi.mock('@/lib/auth', () => ({
  registerAction: vi.fn(),
}))

beforeEach(() => {
  capturedRegisterAction = null
  useActionStateMock.mockImplementation((action, initial) => {
    capturedRegisterAction = action as typeof capturedRegisterAction
    return [initial, vi.fn(), false]
  })
  vi.mocked(registerAction).mockResolvedValue({ ok: true })
  sessionStorage.clear()
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

function renderRegister() {
  const view = render(
    <IntlWrapper locale="en">
      <RegisterPage />
    </IntlWrapper>
  )
  return view
}

function renderRegisterFresh() {
  const view = renderRegister()
  view.unmount()
  return renderRegister()
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

    renderRegister()

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

    renderRegister()

    expect(screen.getByText(/value is not a valid email address/i)).toBeInTheDocument()
    expect(screen.getByText(/String should have at least 8 characters/i)).toBeInTheDocument()

    const email = document.querySelector<HTMLInputElement>('input[name="email"]')
    const password = document.querySelector<HTMLInputElement>('input[name="password"]')
    expect(email?.getAttribute('aria-invalid')).toBe('true')
    expect(password?.getAttribute('aria-invalid')).toBe('true')
  })

  it('falls back to the generic error string on a non-422 failure', async () => {
    setState({ ok: false, error: 'Email already registered' })

    renderRegister()

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/Email already registered/i)
  })

  it('moves keyboard focus to the first error on render', async () => {
    setState({
      ok: false,
      code: 'validation_error',
      fieldErrors: { is_admin: 'Extra inputs are not permitted' },
    })

    renderRegister()
    const error = await screen.findByRole('alert')
    expect(error).toHaveTextContent(/is_admin/i)
    await waitFor(() => expect(document.activeElement).toBe(error))
  })

  it('prefills the email input from the last registered email in sessionStorage', () => {
    sessionStorage.setItem('last_registered_email', 'reader@example.com')

    renderRegisterFresh()

    expect(screen.getByLabelText(/email/i)).toHaveValue('reader@example.com')
  })

  it('stores the submitted email in sessionStorage after a successful register action', async () => {
    renderRegister()
    const formData = new FormData()
    formData.set('email', 'new-reader@example.com')
    formData.set('password', 'password123')

    expect(capturedRegisterAction).not.toBeNull()
    await capturedRegisterAction!({ ok: false }, formData)

    expect(sessionStorage.getItem('last_registered_email')).toBe('new-reader@example.com')
  })

  it('marks the email input invalid after a 422 register response', async () => {
    vi.mocked(registerAction).mockResolvedValue({
      ok: false,
      code: 'validation_error',
      fieldErrors: { email: 'value is not a valid email address' },
    })

    const view = renderRegister()
    const formData = new FormData()
    formData.set('email', 'invalid')
    formData.set('password', 'password123')

    expect(capturedRegisterAction).not.toBeNull()
    const nextState = await capturedRegisterAction!({ ok: false }, formData)
    view.unmount()
    setState(nextState)
    renderRegister()

    expect(screen.getByLabelText(/email/i)).toHaveAttribute('aria-invalid', 'true')
  })

  it('marks the submit button aria-busy while a submission is in flight', () => {
    setState({ ok: false, error: 'Email already registered' }, true)

    renderRegister()
    const button = screen.getByRole('button', { name: /creating/i })
    expect(button).toHaveAttribute('aria-busy', 'true')
  })
})
