/**
 * Fetch wrapper for the FastAPI backend.
 * In server components / actions, the cookie is forwarded automatically via fetch.
 */

const API_URL =
  // In compose both ``API_INTERNAL_URL`` and ``NEXT_PUBLIC_API_URL`` are
  // set (compose sets them explicitly per the matrix in ``docs/ports.md``),
  // so this fallback only triggers for ad-hoc ``pnpm dev`` runs without
  // the env block. Default to the new host port 8007 (per the canonical
  // port-registry file's externalLocal.ai-news-scraper.api.host entry).
  process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8007'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
    /** Response headers (lower-cased). Read `headers.get('retry-after')` etc. */
    public headers?: Headers
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    let code: string | undefined
    try {
      const body = await res.json()
      detail = body.detail || detail
      code = body.code
    } catch {}
    throw new ApiError(res.status, detail, code, res.headers)
  }
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, { ...init, method: 'GET', credentials: 'include' }).then(handle<T>),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, {
      ...init,
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      body: body ? JSON.stringify(body) : undefined,
    }).then(handle<T>),
  /**
   * POST variant that exposes the raw response headers alongside the
   * parsed body. Needed by the auth flow (ADR-015 §15.9) so the
   * server action can forward the API's ``Set-Cookie`` headers —
   * notably the ``auth_refresh`` cookie — to the user's browser.
   * ``api.post`` returns the body only and would drop those headers.
   */
  postWithHeaders: <T>(path: string, body?: unknown, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, {
      ...init,
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
      body: body ? JSON.stringify(body) : undefined,
    }).then(async (res) => {
      if (!res.ok) {
        let detail = res.statusText
        let code: string | undefined
        try {
          const body = await res.json()
          detail = body.detail || detail
          code = body.code
        } catch {}
        throw new ApiError(res.status, detail, code, res.headers)
      }
      const data = (await res.json()) as T
      return { data, headers: res.headers }
    }),
  delete: <T>(path: string, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, { ...init, method: 'DELETE', credentials: 'include' }).then(
      handle<T>
    ),
}

export const API_BASE = API_URL
