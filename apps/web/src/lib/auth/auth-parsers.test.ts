import { describe, it, expect } from 'vitest'
import { parsePydanticFieldErrors } from '@/lib/auth/parsers'

describe('parsePydanticFieldErrors (ADR-015 H1)', () => {
  it('parses a Pydantic extra_forbidden detail array', () => {
    const detail = JSON.stringify([
      {
        type: 'extra_forbidden',
        loc: ['body', 'is_admin'],
        msg: 'Extra inputs are not permitted',
        input: true,
      },
    ])

    const out = parsePydanticFieldErrors(detail)
    expect(out).toEqual({ is_admin: 'Extra inputs are not permitted' })
  })

  it('strips the body/query/path prefix from the visible field name', () => {
    const detail = JSON.stringify([
      {
        type: 'string_too_short',
        loc: ['body', 'password'],
        msg: 'String should have at least 8 characters',
      },
    ])

    const out = parsePydanticFieldErrors(detail)
    expect(out).toEqual({ password: 'String should have at least 8 characters' })
  })

  it('returns null when the body is not a JSON array', () => {
    expect(parsePydanticFieldErrors('Plain text error')).toBeNull()
    expect(parsePydanticFieldErrors('{"detail":"single object"}')).toBeNull()
  })

  it('falls back to "request" when loc is empty', () => {
    const detail = JSON.stringify([{ type: 'value_error', loc: [], msg: 'oops' }])
    const out = parsePydanticFieldErrors(detail)
    expect(out).toEqual({ request: 'oops' })
  })

  it('handles nested loc paths by joining them with dots', () => {
    const detail = JSON.stringify([
      { type: 'value_error', loc: ['body', 'address', 'zip'], msg: 'invalid zip' },
    ])
    const out = parsePydanticFieldErrors(detail)
    expect(out).toEqual({ 'address.zip': 'invalid zip' })
  })
})
