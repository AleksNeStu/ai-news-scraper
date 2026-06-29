import { describe, it, expect, beforeEach, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import {
  DigestNotFoundError,
  getDigest,
  getTodayDigest,
  listDigests,
  todayUtc,
} from "@/lib/api/digest";
import type { Digest, DigestListResponse } from "@ai-news-scraper/shared";

const sampleDigest: Digest = {
  id: "d1",
  user_id: "u1",
  for_date: "2026-06-29",
  overall_summary: "Today in AI...",
  sections: [
    { cluster_id: "eu-ai-act", topic: "EU AI Act", summary: "...", article_ids: ["a1"], rank: 1 },
  ],
  generated_at: "2026-06-29T08:00:00Z",
  delivery_status: "notified",
  email_message_id: null,
};

const sampleList: DigestListResponse = {
  digests: [sampleDigest],
  next_cursor: null,
};

describe("digest api", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("todayUtc returns YYYY-MM-DD", () => {
    expect(todayUtc()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("getTodayDigest hits /digest/today and returns the payload", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue(sampleDigest as never);
    const out = await getTodayDigest();
    expect(out).toEqual(sampleDigest);
    expect(getSpy).toHaveBeenCalledWith("/digest/today");
  });

  it("getTodayDigest maps 404 to DigestNotFoundError", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new ApiError(404, "not found", "missing"));
    await expect(getTodayDigest()).rejects.toBeInstanceOf(DigestNotFoundError);
  });

  it("getDigest encodes the date segment", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue(sampleDigest as never);
    const out = await getDigest("2026/06/29");
    expect(out).toEqual(sampleDigest);
    expect(getSpy).toHaveBeenCalledWith("/digest/2026%2F06%2F29");
  });

  it("getDigest maps 404 to DigestNotFoundError", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new ApiError(404, "not found"));
    await expect(getDigest("2026-06-29")).rejects.toBeInstanceOf(DigestNotFoundError);
  });

  it("listDigests passes cursor and limit as query params", async () => {
    const getSpy = vi.spyOn(api, "get").mockResolvedValue(sampleList as never);
    const out = await listDigests("cursor-abc", 5);
    expect(out).toEqual(sampleList);
    const calledWith: string = getSpy.mock.calls[0][0];
    expect(calledWith).toMatch(/^\/digest\?/);
    expect(calledWith).toContain("cursor=cursor-abc");
    expect(calledWith).toContain("limit=5");
  });
});
