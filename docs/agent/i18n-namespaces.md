# i18n Namespace Taxonomy — Task #32 (P1)

**Audience:** Frontend teammate. This is the build contract for `src/messages/en.json` and `src/messages/ru.json`. Every key listed here MUST exist in both files with identical structure (only translated strings differ).

**Source:** Sourced from a complete sweep of `apps/web/src/**` (pages, components, hooks, lib, layouts). Keys marked **(ICU)** use ICU MessageFormat placeholders — see the `Notes` column for the exact shape.

**Conventions:**
- Namespace keys are camelCase.
- Page sections use nested namespaces: `Articles.Toolbar.all`, `Articles.Toolbar.mustRead`.
- Tier labels live in the top-level `Tiers` namespace (single source of truth — collapses the three duplicate maps in `articles/ArticlesToolbar.tsx`, `articles/buckets.ts`, `dashboard/page.tsx`).
- Server-action error messages live in `Auth.Actions` and `ApiErrors` (server-side resolution).
- ICU pluralization is `{count, plural, =0 {…} =1 {…} other {…}}` where applicable (replaces the 4 hand-rolled ternaries).

---

## Common

| Key | EN string | Notes |
|---|---|---|
| `loading` | Loading… | Brief fallback |
| `refreshing` | Refreshing… | Brief list polling indicator |
| `workingOnIt` | Working on it… | Unsubscribe pending |
| `back` | Back | Generic back-link label |
| `backToArticles` | Back to articles | Article detail |
| `backToBriefs` | Back to briefs | Brief detail |
| `viewAll` | View all → | Dashboard section header link |
| `viewAllBriefs` | View all briefs → | NotificationBell footer |
| `view` | View → | Brief inbox card |
| `read` | Read → | Hero card CTA |
| `original` | Original → | Article detail link to source |
| `retry` | Retry | Generic retry CTA |
| `save` | Save | Reserved |
| `cancel` | Cancel | Reserved |
| `error` | Error | Generic |
| `failedToLoad` | Failed to load | Hook fallback |
| `failedToLoadNotifications` | Failed to load notifications | Hook fallback |
| `failedToLoadCount` | Failed to load count | Hook fallback |
| `dateSeparator` | `·` | Used between metadata chips on article detail |

---

## Header

| Key | EN string |
|---|---|
| `brand` | AI News Search |
| `navScrape` | Scrape |
| `navSearch` | Search |
| `navArticles` | Articles |
| `navBrief` | Brief |
| `navFeeds` | Feeds |
| `navSettings` | Settings |

---

## Tiers (single source of truth — replaces 3 duplicate maps)

| Key | EN string |
|---|---|
| `all` | All |
| `mustRead` | Must Read |
| `recommended` | Recommended |
| `worthALook` | Worth a Look |
| `lowPriority` | Low Priority |

---

## Auth.Login

| Key | EN string |
|---|---|
| `title` | Sign in to AI News Search |
| `email` | Email |
| `password` | Password |
| `submit` | Sign in |
| `submitting` | Signing in... |
| `cooldownRetry` | Retry in {seconds}s | **(ICU)** `{seconds, number}` |
| `cooldownRetryingIn` | Retrying in {seconds}s… | **(ICU)** `{seconds, number}` |
| `noAccount` | No account? |
| `registerLink` | Register |

---

## Auth.Register

| Key | EN string |
|---|---|
| `title` | Create your account |
| `email` | Email |
| `password` | Password (min 8 chars) |
| `submit` | Create account |
| `submitting` | Creating... |
| `haveAccount` | Already have an account? |
| `signInLink` | Sign in |

---

## Auth.Logout

| Key | EN string |
|---|---|
| `label` | Logout |
| `pending` | Logging out… |
| `failed` | Logout failed. Please try again. |

---

## Auth.Actions (server-action error strings)

| Key | EN string | Notes |
|---|---|---|
| `loginFailed` | Login failed | Generic catch |
| `loginTooManyAttempts` | Too many attempts. Try again in {seconds} second{seconds, plural, =1 {} other {s}}. | **(ICU)** — replaces `auth.ts:132` ternary |
| `registrationFailed` | Registration failed | Generic catch |
| `logoutFailed` | Logout failed | From logout helper (display fallback) |

---

## Notifications

| Key | EN string |
|---|---|
| `ariaLabel` | Notifications, {count} unread | **(ICU)** `{count, number}` |
| `menuAriaLabel` | Notifications |
| `recent` | Recent notifications |
| `empty` | No new notifications |

---

## ScoreRing

| Key | EN string | Notes |
|---|---|---|
| `notScored` | Not yet scored | `score === null` |
| `score` | Score {percent} percent, tier {tier} | **(ICU)** `{percent, number}; {tier}` — replaces `ScoreRing.tsx:64` ternary + tier fallback |

---

## Articles.List

| Key | EN string |
|---|---|
| `title` | Articles |
| `empty` | No articles yet. |

## Articles.Toolbar

| Key | EN string |
|---|---|
| `filterGroupAriaLabel` | Filter by tier |
| `groupByTier` | Group by tier |
| `groupByTierAriaLabel` | Group by tier |

> **Tier chip labels** come from `Tiers.*` (e.g. `useTranslations('Tiers')('all')`).
> **Bucket section headings** for grouped view come from `Articles.Buckets.*` (see below) so the lowercase version for the "no X yet" copy stays separate.

## Articles.Buckets

| Key | EN string | Notes |
|---|---|---|
| `emptyMustRead` | No must read articles yet — check back as we score incoming articles. |
| `emptyRecommended` | No recommended articles yet — check back as we score incoming articles. |
| `emptyWorthALook` | No worth a look articles yet — check back as we score incoming articles. |
| `emptyLowPriority` | No low priority articles yet — check back as we score incoming articles. |

> Note: the original code used `TIER_HEADINGS[t].toLowerCase()` to splice into a single sentence. ICU pluralization + per-tier keys is cleaner and survives non-English capitalization rules. Russian translations can use the correct grammatical case per tier without forcing a `.toLowerCase()` equivalent.

## Articles.Detail

| Key | EN string |
|---|---|
| `source` | {domain} | **(ICU)** `{domain}` |
| `indexedAt` | Indexed {relative} | **(ICU)** `{relative}` (formatted via `useFormatter`) |
| `published` | Published {date} | **(ICU)** `{date}` (formatted) |
| `summary` | Summary |
| `topics` | Topics |
| `fullText` | Full text |

---

## Dashboard

| Key | EN string |
|---|---|
| `welcomeHeading` | Welcome back |
| `welcomeSub` | Your personal semantic news library. |
| `recentArticles` | Recent articles |
| `totalArticles` | Total articles |
| `activeFeeds` | Active feeds |
| `indexedToday` | Indexed today |
| `emptyTitle` | No articles yet |
| `emptyBody` | Scrape your first URL or subscribe to an RSS feed to get started. |
| `emptyCta` | Scrape a URL |
| `topPicksHeading` | Today's Top Picks |
| `topPicksSub` | Curated by the AI based on relevance, novelty, and source trust. |
| `heroHeading` | Must Read |
| `emptyMustReadTitle` | Your must-read list is empty |
| `emptyMustReadBody` | Once we score incoming articles, the top picks will appear here. |

> **Tier section headings** come from `Tiers.*`. `dashboard/page.tsx:71` hardcoded "Must Read" again — should also pull from `Tiers.mustRead`.

---

## Brief.Inbox

| Key | EN string | Notes |
|---|---|---|
| `title` | Daily Briefs |
| `loadingAriaLabel` | Loading briefs |
| `disabledTitle` | Daily briefs are temporarily unavailable |
| `disabledBody` | We're working on it — check back soon. |
| `emptyTitle` | No briefs yet |
| `emptyBody` | Your first daily brief will appear here — check back tomorrow. |
| `noNewArticles` | No new articles today. |
| `sections` | {count, plural, =1 {section} other {sections}} | **(ICU)** — replaces `brief/page.tsx:66` ternary |

## Brief.Detail

| Key | EN string | Notes |
|---|---|---|
| `disabledTitle` | Daily briefs are temporarily unavailable |
| `disabledBody` | We're working on it — check back soon. |
| `dailyBriefLabel` | Daily brief · {count, plural, =1 {section} other {sections}} | **(ICU)** — replaces `brief/[date]/page.tsx:79` |
| `overallSummary` | Overall summary |
| `noNewArticlesToday` | No new articles today — your library is quiet. |
| `sources` | Sources |
| `source` | {count, plural, =1 {source} other {sources}} | **(ICU)** — replaces `brief/[date]/page.tsx:120` |
| `articleLink` | Article {shortId} | **(ICU)** `{shortId}` (8-char id prefix) |
| `notFoundTitle` | No brief |
| `notFoundTitleWithDate` | No brief for {date} | **(ICU)** `{date}` formatted long |
| `notFoundBody` | Digests are generated each morning at 08:00 (your local time). |
| `invalidDate` | Invalid date format. |
| `loadingAriaLabel` | Loading brief |

---

## Feeds

| Key | EN string |
|---|---|
| `title` | RSS feeds |
| `urlLabel` | Feed URL |
| `urlPlaceholder` | https://example.com/feed.xml |
| `subscribe` | Subscribe |
| `unsubscribeConfirm` | Unsubscribe? |
| `itemsCount` | {count} items | **(ICU)** `{count, number}` |
| `pollNowAria` | Poll now |
| `unsubscribeAria` | Unsubscribe |
| `empty` | No subscriptions yet. |
| `pollResult` | Polled — {count} new items. | **(ICU)** `{count, number}` |
| `addFailed` | Add failed |

---

## Scrape

| Key | EN string |
|---|---|
| `title` | Scrape a URL |
| `urlLabel` | Article URL |
| `urlPlaceholder` | https://example.com/article |
| `submit` | Scrape |
| `recentScrapes` | Recent scrapes |
| `empty` | No scrapes yet in this session. |
| `failed` | Scrape failed |

---

## Search

| Key | EN string |
|---|---|
| `title` | Semantic search |
| `queryLabel` | Query |
| `queryPlaceholder` | AI regulation in the EU... |
| `submit` | Search |
| `results` | Results |
| `hitsAndMs` | {count} hits · {ms} ms | **(ICU)** `{count, number}; {ms, number}` |
| `noMatches` | No matches. |
| `score` | score {value} | **(ICU)** `{value, number}` (toFixed(3) by caller) |
| `failed` | Search failed |

---

## Settings

| Key | EN string |
|---|---|
| `title` | Settings |
| `account` | Account |
| `accountBody` | Signed in. Account settings live in a future iteration (P1). |
| `openaiKey` | OpenAI key |
| `openaiKeyBody` | Server-side only for MVP. Bring-your-own-key is P1. |
| `summarizer` | Default summarizer |
| `summarizerBody` | gpt-4o-mini (OpenAI). Switchable to Anthropic in P1. |

---

## Unsubscribe

| Key | EN string |
|---|---|
| `loading` | Loading… |
| `title` | Daily brief unsubscribe |
| `workingOnIt` | Working on it… |
| `successTitle` | You've been unsubscribed |
| `successBody` | No more daily briefs will be emailed to you. You can still view them in the dashboard. |
| `alreadyTitle` | You were already unsubscribed |
| `alreadyBody` | No further action needed — the link in your email is still valid, but your preference is already set. |
| `errorTitle` | Couldn't unsubscribe |
| `confirmedAt` | Confirmed at {timestamp}. | **(ICU)** `{timestamp}` formatted by `useFormatter` |
| `backToApp` | Back to AI News Search → |
| `malformedLink` | This unsubscribe link is missing required fields. Please use the link from your email. |
| `networkError` | Couldn't reach the server. Try again from the email. |

---

## Errors (shared HTTP / form error copy)

| Key | EN string |
|---|---|
| `generic` | Something went wrong. Please try again. |
| `rateLimited` | Too many requests. Please slow down. |
| `network` | Network error. Check your connection. |

---

## ApiErrors (typed error class defaults — server-side strings, surfaced via hooks)

| Key | EN string | Used by |
|---|---|---|
| `articlesEmpty` | No articles returned | `ArticlesEmptyError` default |
| `digestDisabled` | Daily briefs are temporarily unavailable | `DigestDisabledError` default |
| `digestNotFound` | No digest for that date | `DigestNotFoundError` default |

> These are the SERVER-SIDE defaults for the typed `ApiError` subclasses. The CLIENT side resolves the user-facing copy from `Brief.Inbox.disabledTitle` / `Brief.Inbox.emptyTitle` etc. when these typed errors are thrown.

---

## Russian translation hints

The author is a Russian speaker. Russian translations should:
- Use "вы" form (formal) — this is a B2C product even if used solo.
- Preserve ICU plural categories (`=1`, `few`, `many`, `other`) — Russian has `few` (1-4) and `many` (5+) forms distinct from `other` (decimals + 0, 11-14). next-intl's plural rule handles this automatically.
- Date format defaults to "5 марта 2026 г." — `useFormatter().dateTime()` with `{ dateStyle: 'long' }` handles this without explicit ICU.
- No literal English allowed. "Loading…" → "Загрузка…", "Logout" → "Выйти", etc.

---

## File structure (Frontend to create)

```
apps/web/src/messages/
├── en.json     # canonical — every key listed here, in English
└── ru.json     # same keys, Russian translations
```

The `en.json` file shape mirrors this document exactly — namespaces as top-level keys, leaves as ICU strings. The TypeScript augmentation in `src/global.ts` derives the type from `en.json`, so adding a new key there is automatically type-safe across the app.
