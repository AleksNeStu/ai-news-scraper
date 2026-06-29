import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import {
  DigestDisabledError,
  DigestNotFoundError,
  getDigest,
  getTodayDigest,
  listDigests,
  todayUtc,
  unsubscribeDigest,
} from "@/lib/api/digest";
import type { Digest, DigestListResponse, UnsubscribeResponse } from "@ai-news-scraper/shared";

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
  afterEach(() => {
    vi.unstubAllGlobals();
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

  it("getTodayDigest maps 404 with digest_disabled code to DigestDisabledError", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new ApiError(404, "off", "digest_disabled"));
    await expect(getTodayDigest()).rejects.toBeInstanceOf(DigestDisabledError);
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

  it("getDigest maps 404 with digest_disabled code to DigestDisabledError", async () => {
    vi.spyOn(api, "get").mockRejectedValue(new ApiError(404, "off", "digest_disabled"));
    await expect(getDigest("2026-06-29")).rejects.toBeInstanceOf(DigestDisabledError);
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

describe("unsubscribeDigest", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockFetchOnce(status: number, body: unknown) {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      statusText: status === 200 ? "OK" : "Error",
      json: async () => body,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);
    return fetchMock;
  }

  it("POSTs form-urlencoded token to /digest/{id}/unsubscribe without credentials", async () => {
    const sample: UnsubscribeResponse = { unsubscribed: true, at: "2026-06-29T12:00:00Z" };
    const fetchMock = mockFetchOnce(200, sample);
    const out = await unsubscribeDigest("d1", "tok-xyz");
    expect(out).toEqual(sample);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/digest\/d1\/unsubscribe$/);
    expect(init.method).toBe("POST");
    expect(init.credentials).toBe("omit");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/x-www-form-urlencoded",
    );
    expect(init.body).toBe("token=tok-xyz");
  });

  it("encodes the digest_id segment", async () => {
    const fetchMock = mockFetchOnce(200, { unsubscribed: false, at: "2026-06-29T12:00:00Z" });
    await unsubscribeDigest("has/slash", "tok");
    const [url] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/digest\/has%2Fslash\/unsubscribe$/);
  });

  it("throws ApiError with status + code on non-2xx", async () => {
    mockFetchOnce(401, { detail: "expired token", code: "token_expired" });
    await expect(unsubscribeDigest("d1", "bad-tok")).rejects.toMatchObject({
      status: 401,
      code: "token_expired",
    });
  });
});
