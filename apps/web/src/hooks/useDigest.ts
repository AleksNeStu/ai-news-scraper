"use client";

/**
 * React hooks for AI Brief digests. Plain `useState` + `useEffect` to match
 * the existing pages (no QueryProvider wired in root layout).
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import {
  getDigest,
  getTodayDigest,
  listDigests,
  DigestNotFoundError,
} from "@/lib/api/digest";
import type { Digest, DigestListResponse } from "@ai-news-scraper/shared";

export interface UseQueryState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

function useAsync<T>(fn: () => Promise<T>, deps: ReadonlyArray<unknown>): UseQueryState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fn()
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((e) => {
        if (cancelled) return;
        // 404 means "no digest yet" — not a hard error, surface as null data.
        if (e instanceof DigestNotFoundError) {
          setData(null);
        } else if (e instanceof ApiError) {
          setError(e.message);
        } else {
          setError("Failed to load");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { data, loading, error, reload };
}

/** Today's digest (UTC). Returns `data: null` when none exists yet. */
export function useTodayDigest() {
  return useAsync<Digest | null>(() => getTodayDigest(), []);
}

/** Digest for a specific date (`YYYY-MM-DD`). */
export function useDigest(date: string | null) {
  return useAsync<Digest | null>(
    () => (date ? getDigest(date) : Promise.resolve(null)),
    [date],
  );
}

/** Cursor-paginated digest history. */
export function useDigestList(limit = 20) {
  return useAsync<DigestListResponse>(() => listDigests(undefined, limit), [limit]);
}
