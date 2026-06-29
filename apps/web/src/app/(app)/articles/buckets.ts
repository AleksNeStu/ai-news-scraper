/**
 * Pure helpers extracted from `articles/page.tsx` so they can be unit-tested
 * without standing up a Next.js server-component render in jsdom.
 *
 * Keeping them in a separate file (no `"use server"` / `"use client"` directive)
 * means both the Server Component and the test suite can `import` them.
 */

import type { Article, Tier } from "@ai-news-scraper/shared";

export const TIER_ORDER: readonly Tier[] = ["must_read", "recommended", "worth_a_look", "low_priority"];

export const TIER_HEADINGS: Record<Tier, string> = {
  must_read: "Must Read",
  recommended: "Recommended",
  worth_a_look: "Worth a Look",
  low_priority: "Low Priority",
};

export function isTier(v: unknown): v is Tier {
  return typeof v === "string" && (TIER_ORDER as readonly string[]).includes(v);
}

/** Group articles into tier buckets, preserving insertion order within a bucket. */
export function bucketByTier(items: Article[]): Record<Tier, Article[]> {
  const out: Record<Tier, Article[]> = {
    must_read: [],
    recommended: [],
    worth_a_look: [],
    low_priority: [],
  };
  for (const a of items) {
    if (a.tier && out[a.tier]) out[a.tier].push(a);
  }
  return out;
}
