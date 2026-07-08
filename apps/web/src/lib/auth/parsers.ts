/**
 * Pure parsers for API error shapes.
 *
 * Lives outside the `'use server'` boundary — Next.js compiles every
 * export of a `'use server'` module as a Server Action and rejects
 * sync functions with `Server Actions must be async functions`.
 * `parsePydanticFieldErrors` is a deterministic, side-effect-free
 * transformation of a Pydantic v2 detail array into a flat
 * `{ field: message }` map, so it belongs in a regular module
 * that both server actions and client components can import.
 *
 * ADR-015 H1 (mass-assignment 422 surface) — the parser strips the
 * leading `body`/`query`/`path` segment from `loc` so the visible
 * field reads "is_admin: …" instead of "body.is_admin: …".
 */

export function parsePydanticFieldErrors(message: string): Record<string, string> | null {
  try {
    // ApiError.message is the raw `detail` value (a JSON string of the array,
    // or a string if the backend returned a flat error). Try parse first.
    const parsed = JSON.parse(message)
    if (!Array.isArray(parsed)) return null
    const out: Record<string, string> = {}
    for (const item of parsed) {
      if (!item || typeof item !== 'object') continue
      const loc = Array.isArray(item.loc) ? item.loc : []
      // Drop leading "body" / "query" / etc. — the visible field is the tail.
      const visibleLoc = loc.filter((p: unknown) => p !== 'body' && p !== 'query' && p !== 'path')
      const field = visibleLoc.join('.') || 'request'
      const msg = typeof item.msg === 'string' ? item.msg : 'Invalid value'
      out[field] = msg
    }
    return Object.keys(out).length > 0 ? out : null
  } catch {
    return null
  }
}
