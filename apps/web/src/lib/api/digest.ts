/**
 * Typed client for the AI Brief digest endpoints.
 *
 * Endpoints (per `.agent/adr/012-ai-brief.md` §12.2):
 *   GET  /digest/today
 *   GET  /digest/{for_date}
 *   GET  /digest?cursor=...&limit=...
 *
 * All routes require the existing JWT cookie.
 */

import { api, ApiError } from "../api";
import type { Digest, DigestListResponse } from "@ai-news-scraper/shared";

export class DigestNotFoundError extends ApiError {
  constructor(message = "No digest for that date") {
    super(404, message, "digest_not_found");
    this.name = "DigestNotFoundError";
  }
}

/** Today (UTC) as `YYYY-MM-DD`. */
export function todayUtc(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Today's digest for the caller. 404 throws `DigestNotFoundError`. */
export async function getTodayDigest(): Promise<Digest> {
  try {
    return await api.get<Digest>("/digest/today");
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw new DigestNotFoundError();
    throw e;
  }
}

/** Digest for a specific UTC date (`YYYY-MM-DD`). */
export async function getDigest(forDate: string): Promise<Digest> {
  try {
    return await api.get<Digest>(`/digest/${encodeURIComponent(forDate)}`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) throw new DigestNotFoundError();
    throw e;
  }
}

/** Cursor-paginated history. `next_cursor === null` when no more pages. */
export async function listDigests(
  cursor?: string,
  limit = 20,
): Promise<DigestListResponse> {
  const params = new URLSearchParams();
  if (cursor) params.set("cursor", cursor);
  params.set("limit", String(limit));
  const qs = params.toString();
  return api.get<DigestListResponse>(`/digest?${qs}`);
}
