/**
 * Fetch wrapper for the FastAPI backend.
 * In server components / actions, the cookie is forwarded automatically via fetch.
 */

const API_URL = process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8082";

export class ApiError extends Error {
  constructor(public status: number, message: string, public code?: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    let code: string | undefined;
    try {
      const body = await res.json();
      detail = body.detail || detail;
      code = body.code;
    } catch {}
    throw new ApiError(res.status, detail, code);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, { ...init, method: "GET", credentials: "include" }).then(handle<T>),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, {
      ...init, method: "POST", credentials: "include",
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
      body: body ? JSON.stringify(body) : undefined,
    }).then(handle<T>),
  delete: <T>(path: string, init?: RequestInit) =>
    fetch(`${API_URL}${path}`, { ...init, method: "DELETE", credentials: "include" }).then(handle<T>),
};

export const API_BASE = API_URL;
