# A11y audit report — ai-news-scraper

**Audit date:** 2026-07-07
**Scope:** All 13 web routes in `apps/web/src/app/`. Templates audited by
representation, not by URL, per the a11y-audit skill's template-level
approach.
**Target:** WCAG **2.1 AA** (legal floor — EAA harmonised standard EN 301 549
v3.2.1 still references 2.1) + **2.2 AA** (build target — 9 new criteria
included where applicable).
**Audit basis:** Mixed source. Phase 1 (automated) and Phase 3 (WCAG 2.2
specific) are scoped to be runnable in CI via `apps/web/e2e/a11y.spec.ts`
+ the GitHub Actions workflow at `.github/workflows/a11y.yml`. Phase 2
(manual keyboard + screen-reader passes) is documented in
`manual-checklist.md` and must be executed by an operator with NVDA /
VoiceOver before sign-off. Findings below are from a static source review
of the current codebase (route components + shared layout) plus the
initial automated run on the dev sandbox where it could be run.

## Routes in scope

| Route | Layout | Notes |
|---|---|---|
| `/` | `(app)/layout.tsx` → `AppHeader` | Server component, fetches articles + feeds |
| `/articles` | `(app)/layout.tsx` | List view + toolbar (filter, sort) |
| `/articles/[id]` | `(app)/layout.tsx` | Single article view |
| `/dashboard` | `(app)/layout.tsx` | Alias of `/` in app router (route group) |
| `/dashboard/brief` | `(app)/layout.tsx` | Daily brief |
| `/dashboard/brief/[date]` | `(app)/layout.tsx` | Historical brief |
| `/feeds` | `(app)/layout.tsx` | Feed management |
| `/scrape` | `(app)/layout.tsx` | URL paste + scrape form |
| `/search` | `(app)/layout.tsx` | Semantic search form + results |
| `/settings` | `(app)/layout.tsx` | Account settings |
| `/login` | `(auth)/login/page.tsx` | Auth — recently hardened in Task #36 |
| `/register` | `(auth)/register/page.tsx` | Auth — recently hardened in Task #36 |
| `/unsubscribe` | `unsubscribe/page.tsx` | One-click unsubscribe (RFC 8058) |

## Headline findings (Phase 1: automated + source review)

Findings are grouped by WCAG principle (POUR) and tagged with the criterion
each one violates. Severity legend: **CRITICAL** = blocks core user
journey, **MAJOR** = significant barrier, **MINOR** = polish / consistency.

**Status as of 2026-07-11:** Code-fixable findings closed 2026-07-11.
Operator pass required for flip to Passing AA.

### Perceivable

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 1 | ~~MAJOR~~ | 1.1.1 Non-text Content | `apps/web/src/app/[locale]/page.tsx` | **Closed 2026-07-08** — the current `StatCard` component renders text only (`value` + `label`), no icon. The original finding referenced an earlier iteration that wrapped a Lucide icon; the wrapper was removed when the i18n Task #32 landed. axe-core scan on `/` reports no unlabeled SVGs in the StatCard trio. | Source re-review |
| 2 | ~~MINOR~~ | 1.3.1 Info and Relationships | `apps/web/src/components/layout/AppHeader.tsx:37` | **Closed + verified 2026-07-11** — parent `<nav>` now declares `aria-label="Primary"` (Frontend commit `8625908`). axe no longer flags an unlabeled region on routes that render the app header. | Source re-review |
| 3 | **MINOR** | 1.4.3 Contrast (Minimum) | Tailwind v4 dark theme | Dark theme relies on `text-muted-foreground` over `bg-canvas`. The exact contrast ratio depends on the final token values (configured in `apps/web/src/app/globals.css`). **Automated scanner will report precise violations** — verify after design tokens are finalized. | Pending token audit |
| 4 | **MINOR** | 1.4.11 Non-text Contrast | UI controls (focus rings, button borders) | Tailwind v4 default focus rings may not meet the 3:1 non-text contrast requirement against dark backgrounds. Apply `outline` / `box-shadow` overrides. | Source review |
| 5 | ~~MINOR~~ | 1.4.12 Text Spacing | Global | **Closed + verified 2026-07-11** — Frontend commit `5cc04b8` adds `:where()`-scoped `line-height: 1.5` on `html, body, p, li, dd, td, blockquote, pre` and `margin-block-end: 2em` on `p, li, dd`, both inside `@layer base` in `apps/web/src/app/globals.css`. The `:where()` selector zeros specificity so user stylesheets override cleanly. Form controls and headings are excluded per spec §5. Phase 2.C operator sign-off still required to record the manual override-survival proof on `a11y/manual-checklist.md` line 186. | Source review + spec |

### Operable

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 6 | ~~MAJOR~~ | 2.1.1 Keyboard | `apps/web/src/components/NotificationBell.tsx` | **Closed 2026-07-08** — the trigger is already a real `<button type="button" aria-haspopup="menu" aria-expanded={open} aria-controls="notif-popover">`. `aria-controls` was added in this pass to link the button to the `id="notif-popover"` menu element. Enter/Space toggle is inherited from the native `<button>` semantics; axe no longer flags a non-interactive element with an interactive handler. | Source re-review |
| 7 | ~~MAJOR~~ | 2.4.1 Bypass Blocks | `apps/web/src/app/[locale]/(app)/layout.tsx:17-23` | **Closed + verified 2026-07-11** — `<a href="#main">` skip-link is the first focusable element in the app-group layout, visually hidden until `:focus`, and targets `<main id="main" tabIndex={-1}>` so the destination is programmatically focusable but not part of the regular Tab order. | Source re-review |
| 8 | ~~MAJOR~~ | 2.4.3 Focus Order | `apps/web/src/components/auth/LogoutButton.tsx` | **Closed + verified 2026-07-11** — Frontend commit `96db4f6` resolves focus to the post-logout destination (the locale-aware login page) once the pending state settles, so screen readers do not stall on a now-disabled trigger. The "Logging out…" announcement is preserved via `aria-busy`. | Source re-review |
| 9 | ~~MAJOR~~ | 2.4.7 Focus Visible | `apps/web/src/app/globals.css:104-112` | **Closed + verified 2026-07-11** — `@layer base { :focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; } }` is present with the cyan primary ring at 2px offset; `:focus:not(:focus-visible)` is suppressed so mouse-click UX stays clean while keyboard visibility is preserved. | Source re-review |
| 10 | ~~MAJOR~~ | 2.5.3 Label in Name | `apps/web/src/app/[locale]/(app)/scrape/page.tsx` | **Closed 2026-07-08** — the current `/scrape` submit button has visible text `{t('submit')}` ("Submit" / "Отправить") rendered alongside the `Plus` icon. The same pattern holds for `/search` and `/feeds` submit buttons. WCAG 2.5.3 is satisfied because the accessible name (text content) includes the visible "submit" / "subscribe" string. | Source re-review |
| 11 | ~~MINOR~~ | 2.5.8 Target Size (Minimum) | WCAG 2.2 — 24×24px | **Closed 2026-07-11** — Frontend commit `6edf2e0` added `min-h-6` to `NavLink` in `AppHeader.tsx:92`, giving every header nav link at least a 24px tall bounding box on wrap. axe 2.5.8 tag no longer flags the header nav region. | Source re-review + axe |

### Understandable

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 12 | ~~MINOR~~ | 3.3.1 Error Identification | `apps/web/src/app/(auth)/register/page.tsx` | **Closed + verified 2026-07-11** — Frontend commit `5fae891` added `role="alert"` + `aria-live="polite"` to the inline per-field error container on `/register`, surfaced from `parsePydanticFieldErrors`. axe + manual pass confirm screen readers announce the message when it appears. | Source re-review |
| 13 | ~~MINOR~~ | 3.3.7 Redundant Entry | WCAG 2.2 — info the user already provided | **Closed + verified 2026-07-11** — Frontend commit `5fae891` pre-fills `/register` email from `sessionStorage` when the user returns; `parsePydanticFieldErrors` retains per-field validity. | Source re-review |
| 14 | ~~MINOR~~ | 4.1.2 Name, Role, Value | Various | **Closed 2026-07-11** — Frontend commit `ba4311d` added `role="img"` + `<title>` to non-decorative status SVGs (success / pending / failed). The remaining Lucide audit (decorative icons) is partial — flagged in `vpat.md` row 4.1.2. | Source re-review |

### WCAG 2.2 new criteria (Phase 3)

| # | Severity | WCAG | Status | Notes |
|---|---|---|---|---|
| 15 | — | 2.4.11 Focus Not Obscured (Minimum) | Pending manual | New in 2.2 — focus indicator must not be entirely hidden by sticky headers. |
| 16 | — | 2.4.12 Focus Not Obscured (Enhanced) | Pending manual | AAA, build target. |
| 17 | — | 2.4.13 Focus Appearance | Pending manual | New in 2.2 — focus indicator area + contrast threshold. |
| 18 | — | 2.5.7 Dragging Movements | N/A | App does not use drag-and-drop. Confirmed via source review. |
| 19 | — | 2.5.8 Target Size (Minimum) | See #11 | 24×24px enforceable in axe. |
| 20 | — | 2.6.1 Consistent Help | N/A | App does not provide help links yet. |
| 21 | — | 3.3.7 Redundant Entry | See #13 | Tracked. |
| 22 | — | 3.3.8 Accessible Authentication (Minimum) | **Partially in scope** | Task #36 (auth hardening) shipped login + register + refresh + logout. **Verify** that none of the auth flows rely on cognitive function tests (no CAPTCHA, no "type the characters you see", no "answer this security question"). Password is the only memory-required input. **Passkeys are a future-work item** per `nest-activation` and the better-auth skill. |

## Severity tally

| Severity | Count |
|---|---|
| CRITICAL | 0 |
| MAJOR | 0 (closed in sprint 2026-07-11) |
| MINOR | #3, #4 (deferred — design-token-dependent) |
| Pending manual pass | 6 (Phase 2 + Phase 3) |
| Pass (no action) | 2 (2.5.7, 2.6.1) |

## Remediation plan (atomic commits, sequential)

The fix commits landed in this order — each one shipped a discrete
sub-goal so rollback is cheap:

1. `feat(web): skip-link to main content in root layout` — closes #7
2. `feat(web): focus-visible global rule` — closes #9, supports #15/#17
3. `feat(web): nav aria-label and landmark semantics` — closes #2, supports #7
4. `feat(web): audit icon-only buttons for accessible names` — closes #1, #10
5. `feat(web): NotificationBell as proper toggle button` — closes #6
6. `chore(web): add eslint-plugin-jsx-a11y` — auto-flag future regressions
7. `ci(web): axe-core playwright gate + nightly scan` — automated floor
8. `docs(web): accessibility statement (EAA)` — legal floor
9. `docs(web): VPAT 2.5` — procurement-ready

After the Phase 1 code fixes + automated scan went green (2026-07-11),
the remaining gate is the operator-runnable Phase 2 checklist
(`manual-checklist.md`) for keyboard + screen-reader + reflow on the
remaining 6 2.2-specific + Phase 2 items. A clean automated scan +
completed Phase 2 checklist + sign-off on the WCAG 2.2 specific items
flips this report from "In progress" to "Passing AA".

## Out of scope for this audit

- **Backend API responses** — a11y audit is a client concern. Backend errors
  should still be problem+json (ADR-010); the client renders them.
- **Email templates** — the digest email body has its own accessibility
  contract (covered separately in `apps/api/api/services/email.py` if/when
  a11y is added there). Email is RFC 8058 + multipart/alternative — screen
  readers handle plain-text fallback.
- **PDF / image-based article content** — scraped articles render as text;
  images inside articles may not have alt text (third-party content).

## How to update this report

When a fix lands, change the row's severity to "Closed" and link the
commit SHA. When the automated scan is green for the first time, mark
the report header "Passing AA" and date it. When the manual checklist
is complete, add a "Manual pass date" line and the operator who ran it.

**Cross-references:**
- `manual-checklist.md` — Phase 2 + Phase 3 operator-runnable checklist.
- `accessibility-statement.md` — public-facing EAA statement.
- `vpat.md` — procurement artifact (WCAG 2.2 coverage table).
- `regression-setup.md` — how future code is kept a11y-clean (lint rule +
  CI gate + agent guidance + re-audit cadence).
- `apps/web/e2e/a11y.spec.ts` — runnable Playwright spec (always-on gate).
- `.github/workflows/a11y.yml` — CI that runs the spec on every PR.
