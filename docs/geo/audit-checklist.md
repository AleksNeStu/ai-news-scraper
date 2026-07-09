# GEO 5-Layer Audit — ai-news-scraper

> **Port note (2026-07-08):** every ``localhost:3807`` URL in this document
> now means ``localhost:3807`` per the canonical port-registry file's
> ``externalLocal.ai-news-scraper`` entry. The substitution is applied below;
> update new entries with the new port.

This checklist documents what shipped for Task #28 (GEO readiness)
and what is deferred. Each item is a checkbox a future operator can
run through; every shipped item has a verification command. Deferred
items list the rationale so they aren't lost.

Source ADR: `.agent/ADR/018-geo-readiness.md`.

---

## Layer 1: Discovery

Files that tell engines *what the site is* and *which pages exist*.

- [x] **`/llms.txt` exists** — returns the 4-rule format
      (`# Title`, blockquote summary, then `## Section` blocks per
      locale with bulleted links).
- [x] **`/llms.txt` allowlist** — explicit `LLMS_ROUTE_SECTIONS`
      constant in `packages/shared/src/structured-data.ts:226-252`,
      mirrored against `apps/web/src/app/sitemap.ts`. Internal and
      auth-only routes are deliberately excluded.
- [x] **`/robots.txt` allows AI user-agents** — `GPTBot`, `ClaudeBot`,
      `Claude-User`, `PerplexityBot`, `Google-Extended`,
      `Applebot-Extended` are each listed explicitly. Bare
      `User-agent: *` is `Allow: /` so any engine with a token we
      missed is still permitted.
- [x] **Auth gating is NOT done in `/robots.txt`** — auth-only paths
      (`/login`, `/register`, the `(auth)` group, session-only
      dashboard subtree) are NOT disallowed in robots.txt by design.
      Crawling them returns a redirect to `/login` at request time
      (gated by `apps/web/middleware.ts` `PUBLIC_PATHS` /
      `PUBLIC_PREFIXES`), not a 200. `robots.txt` cannot enforce
      auth; the file's own header comment (line 7-8 of `robots.ts`)
      is explicit about this.
- [x] **`/robots.txt` references the sitemap** — the
      `Sitemap: <siteUrl>/sitemap.xml` line is present.
- [x] **`/sitemap.xml` lists the static public surface, per locale**
      — `apps/web/src/app/sitemap.ts` enumerates the 11 routes from
      the allowlist with one `<url>` block per locale (22 entries
      total). Per-article URLs (`/articles/[id]`) and per-date
      briefs (`/dashboard/brief/[date]`) are **excluded by design**
      — they would explode the sitemap and engines discover them
      via normal crawling plus the canonical / llms.txt references.
      See `apps/web/src/app/sitemap.ts:9-13` for the rationale
      comment.
- [x] **`Cache-Control` on `/llms.txt`** — set to
      `public, max-age=3600, s-maxage=3600`. ETag is **deferred**
      (Next.js Route Handler responses don't get one without a
      manual `NextResponse` header + builder-input hash); not a hard
      requirement since `Cache-Control` covers freshness.
- [ ] **`llms-full.txt`** — deferred. Reasoning in ADR-018 §18.6:
      no engine treats it as a hard requirement today, and the
      per-page markdown rendering cost is non-trivial.
- [ ] **AI-crawler rate-limiting** — deferred. Adds reverse-proxy
      state and a per-engine token bucket. Re-evaluate when crawler
      traffic becomes a measurable share of the load.

Verification:

```bash
# 1. /llms.txt returns the 4-rule format.
curl -fsS http://localhost:3807/llms.txt | head -40
# Expect: "# <name>", blank line, "> <summary>", blank line,
# then `## <heading> (en)` / `## <heading> (ru)` blocks, each
# with `- [Title](url): description` links.

# 2. Cache headers on /llms.txt.
curl -fsSI http://localhost:3807/llms.txt | grep -i 'cache-control'
# Expect: Cache-Control: public, max-age=3600, s-maxage=3600 (no
# ETag expected — see Layer 1 bullets above).

# 3. /robots.txt allows the named AI user-agents and points at the sitemap.
curl -fsS http://localhost:3807/robots.txt | grep -E 'GPTBot|ClaudeBot|PerplexityBot|Google-Extended|Sitemap:'

# 4. /sitemap.xml lists every public route per locale.
curl -fsS http://localhost:3807/sitemap.xml | grep -c '<loc>'
# Expect: >= N×L (N public routes, L locales). Default = 11 routes × 2 locales = 22.

# 5. Allowlist parity check (local).
diff <(curl -fsS http://localhost:3807/sitemap.xml | grep -oE '/[a-z]?[a-z/-]*' | sort -u) \
     <(curl -fsS http://localhost:3807/llms.txt | grep -oE 'https?://[^)]+' \
       | sed -E 's|^https?://[^/]+||' | sort -u)
# Expect: empty diff (or differences only in items that are legitimately in
# the sitemap but not llms.txt, e.g. the API endpoint family).
```

---

## Layer 2: Structured data

JSON-LD payloads that let engines classify each page.

- [x] **`Organization` JSON-LD on the root layout**
      (`apps/web/src/app/[locale]/layout.tsx`) — `name`, `url`,
      `logo`, `sameAs` (canonical social profile URLs), `description`.
- [x] **`WebSite` JSON-LD on the root layout** — `name`, `url`,
      `inLanguage` (matching `[locale]`), `potentialAction`
      `SearchAction` pointing at the in-app search route.
- [x] **`SoftwareApplication` JSON-LD on `/dashboard`** — `name`,
      `url`, `applicationCategory`, `operatingSystem`,
      `description`, `offers` (where applicable). Emitted on the
      dashboard surface only — that's where the product is described
      as something the user is using.
- [x] **`Article` JSON-LD on `/articles/[id]`** — `headline`,
      `datePublished`, `dateModified`, `author`, `image`,
      `mainEntityOfPage`, `inLanguage`, optional `description`,
      `keywords`.
- [x] **`BreadcrumbList` on hierarchy-bearing pages** —
      `/articles/[id]`, `/dashboard/brief/[date]`, plus the
      dashboard root when a sub-route is rendered.
- [x] **`CollectionPage` on `/articles`** — `name`, `url`,
      `description`, `inLanguage`.
- [x] **Emitted via a typed `<StructuredData>` component** — wraps
      a discriminated `StructuredDataNode` union from
      `packages/shared/src/structured-data.ts:129-135`, so the JSX
      boundary catches any payload that doesn't match the schema.
- [ ] **`FAQPage`** — deferred. No FAQ content on the marketing or
      product pages; would be invented, not earned. Skip until there
      is real FAQ content worth marking up.
- [ ] **`ItemList`** — deferred. The articles list naturally reads
      as `CollectionPage`, which is what we ship; ItemList is a
      duplicate node type for the same content.
- [ ] **`ProfilePage`** — deferred. No user-facing profile pages in
      MVP scope.
- [ ] **`Product`, `Review`, `HowTo`** — not applicable (the
      product is a SaaS research tool, not a commerce or recipe
      surface).

Verification:

```bash
# 1. JSON-LD blocks on each route.
for url in "/" "/dashboard" "/articles" "/articles/1" "/dashboard/brief/2026-07-08"; do
  echo "=== $url ==="
  curl -fsS "http://localhost:3807${url}" | grep -oE '"@type":"[^"]+"' | sort -u
done
# Expect:
#   /                    -> Organization, WebSite
#   /dashboard           -> SoftwareApplication (+ WebSite from layout)
#   /articles            -> CollectionPage (+ WebSite from layout)
#   /articles/1          -> Article, BreadcrumbList (+ WebSite from layout)
#   /dashboard/brief/... -> BreadcrumbList (+ WebSite from layout)

# 2. inLanguage matches [locale] on every payload that carries the field.
for url in "/articles/1" "/ru/articles/1"; do
  echo "=== $url ==="
  curl -fsS "http://localhost:3807${url}" \
    | grep -oE '"inLanguage":"[^"]+"' | sort -u
done
# Expect: locale-segmented values match the path segment.

# 3. External validators (run on a deployed URL, not local).
# - Google Rich Results Test:
#     https://search.google.com/test/rich-results
#   Paste one URL per schema-bearing route. Expect "Eligible" on
#   Organization, WebSite, Article, BreadcrumbList.
# - Bing Markup Validator, Schema.org validator — same payload.
```

---

## Layer 3: Metadata

Per-page metadata that closes the SEO/social-card gap.

- [x] **`canonical`** on every public route — one canonical URL per
      page, even when two-locale routing means two live URLs exist.
- [x] **`og:title`, `og:description`, `og:type`, `og:url`** on every
      public route. `og:type` is `website` for marketing/list pages
      and `article` on `/articles/[id]`.
- [x] **`og:locale`** on every public route — matches the `[locale]`
      segment so the social-share renderer uses the right language.
- [x] **`twitter:card`, `twitter:title`, `twitter:description`** on
      every public route — `summary_large_image` for the homepage
      and dashboard, `summary` elsewhere.
- [x] **Metadata flows through the Messages catalog** — see commit
      `f302e87` ("fix(i18n): route metadata title/description
      through Messages catalog"). No English string-compared against
      locale; metadata is locale-resolved.
- [ ] **`og:image` per page** — deferred. Today's social shares
      use a single static fallback image at
      `apps/web/public/og-default.png`. Per-page OG image generation
      is a separate task (probably `@vercel/og` or its self-hosted
      analogue), gated on a design pass.

Verification:

```bash
# 1. canonical + og:* + twitter:* on every public route.
for url in "/" "/dashboard" "/articles" "/articles/1"; do
  echo "=== $url ==="
  curl -fsS "http://localhost:3807${url}" \
    | grep -oE '<(link|meta) [^>]*(canonical|og:|twitter:)[^>]*>' \
    | head -20
done
# Expect: a single <link rel="canonical" href="...">, an
# <meta property="og:title">, og:description, og:type, og:url,
# og:locale, and a twitter:card, twitter:title, twitter:description.

# 2. Canonical matches the in-locale URL (no cross-locale leakage).
curl -fsS http://localhost:3807/articles/1 | grep -oE 'rel="canonical"[^>]*'
curl -fsS http://localhost:3807/ru/articles/1 | grep -oE 'rel="canonical"[^>]*'
# Expect: canonical hrefs that include the matching locale segment
# (or omit the segment for the default locale under
# localePrefix: 'as-needed').
```

---

## Layer 4: Social proof / knowledge graph

External presence that engines and human searchers use to triangulate
the project.

- [ ] **Wikipedia entry** — deferred. The product is small enough
      that an immediate Wikipedia entry is unlikely to clear the
      notability threshold. Re-evaluate in 6 months after the
      product has shipped and accumulated external citations.
- [ ] **Wikidata entity** — deferred for the same reason as above.
- [ ] **Crunchbase / Product Hunt / vendor directories** — deferred.
      Useful for SEO equity; out of scope for the current GEO MVP.
- [ ] **External editorial citations** — deferred. Earned over
      time; not something we can ship directly.
- [ ] **`sameAs` profile links in `Organization` JSON-LD** —
      shipped (see Layer 2). Today this anchors the only social
      graph signal we control.

Rationale: Layer 4 is largely about external presence that the
product cannot directly create — it must be earned. The MVP
deliverable (the `sameAs` payload) is the only direct control
surface and is shipped.

Verification:

```bash
# 1. Inspect the Organization JSON-LD's sameAs array.
curl -fsS http://localhost:3807/ \
  | grep -oE '"sameAs":\[[^]]+\]'
# Expect: a non-empty array of absolute profile URLs (canonical
# GitHub / X / etc.). Subject to the private-leak gate.
```

---

## Layer 5: Citation tracking

Measurement of whether the engines are *actually* citing us. This is
the layer we cannot ship on day one of indexing; we need a baseline
first.

- [ ] **Share-of-Model measurement pipeline** — deferred. The
      pipeline submits a representative query set to ChatGPT /
      Claude / Perplexity on a schedule and counts citations of our
      canonical URLs. Implementation requires picking a query
      harvest strategy (manual per period, or a search-derived
      harvest) and an analytics surface to write the counts to.
- [ ] **First-model-citation dashboard** — deferred. Even when the
      pipeline exists, the dashboard is a separate task: a single
      counter per engine, plus a query-over-time chart.
- [ ] **Re-crawl signal loop** — deferred. After citation data
      arrives, we may need to refresh the `/llms.txt` section
      headings to highlight the queries we are most-cited for.
      Implementation gated on data.

Rationale: without a baseline, any measurement we ship on day one
captures noise. The first 4–6 weeks of being indexed is the
baseline; the pipeline is wired in week 6 and the dashboard follows.

---

## Cross-cutting checks

Quick sanity gates that catch class-of-bug regressions regardless of
which layer is touched.

- [x] **`pnpm build` passes** — no TypeScript errors, no RSC
      boundary violations from the JSON-LD payload.
- [x] **`pnpm lint` passes** — no eslint disable comments added to
      slip the StructuredData component past react/no-danger.
- [x] **`pnpm test` passes** — locale propagation, JSON-LD payload
      shape, and allowlist coverage have unit tests.
- [x] **No internal-infrastructure identifiers in JSON-LD output**
      — the `scripts/private-leak-check.sh` gate runs against
      `git diff --cached` in pre-commit and against the rendered
      HTML in the deployment runbook.
- [x] **No `(auth)/*` or `/api/*` (the route class, not the
      documented endpoints) in the llms.txt allowlist** — the
      allowlist constant is the source of truth and excludes both.
- [x] **All schemas that carry `inLanguage` set it to the active
      `[locale]`** — verified per Layer 2 step 2.
- [x] **`Cache-Control` header on `/llms.txt`** — verified per
      Layer 1 step 2.
- [x] **Locale-suffixed section headings in `/llms.txt`** — `## Main
      pages (en)` / `## Main pages (ru)` so a crawler that parses
      linearly does not have to guess path prefixes.
- [x] **External validators pass** — Google Rich Results Test,
      Bing Markup Validator, Schema.org validator all return
      "Eligible" / no-errors.

Verification:

```bash
# 1. CI gates (run from repo root).
cd apps/web
pnpm install --frozen-lockfile
pnpm lint
pnpm test
pnpm build

# 2. Private-leak gate (local + CI).
bash scripts/private-leak-check.sh --self-test     # confirm the gate
                                                     # itself is healthy
git diff --cached | bash scripts/private-leak-check.sh
# Expect: exit 0 on every diff chunk.

# 3. End-to-end smoke against the local server.
pnpm dev &
sleep 5
# Re-run every Layer 1 / 2 / 3 verification block above.
```

---

## Out-of-scope (documented for future work)

Items explicitly deferred by ADR-018; flagged here so a future
operator can pick them up without re-investigating.

| Item | Status | Rationale | Trigger to revisit |
|---|---|---|---|
| `llms-full.txt` | Deferred | No engine requires it today; rendering cost is non-trivial. | After citation-tracking data shows the 4-rule format is the bottleneck. |
| Per-page OG image generation | Deferred | Static fallback ships today; pipeline wants a design pass. | Once a designer approves the OG card template. |
| Share-of-Model pipeline | Deferred | Baseline must exist first. | After 4–6 weeks of indexed baseline. |
| AI-crawler rate-limiting | Deferred | No measured bot pressure yet. | When crawler traffic is a measurable share of bandwidth. |
| Wikipedia / Wikidata entries | Deferred | Notability threshold unclear. | 6-month review. |
| `FAQPage`, `ItemList`, `ProfilePage` JSON-LD | Deferred | No matching content; would be invented not earned. | When the content actually exists. |
| Third locale (`[locale]/de`, etc.) | Out of scope here | Coordinated change across `LlmsLocale`, routing, allowlist, locale config. | When product strategy chooses the locale. |

---

## How to use this checklist

1. Run through each layer top-to-bottom on every release that
   touches discovery, structured data, or metadata.
2. Treat any unchecked "shipped" item as a regression — it should
   have been re-verified before merge.
3. Treat any new "deferred" item as scope creep if it slips into a
   routine GEO PR. Add a follow-up ADR instead, then expand the
   checklist when the follow-up ships.
4. The verification commands are runnable against
   `http://localhost:3807` (after `pnpm dev`) or against a deployed
   URL by substituting the origin.
