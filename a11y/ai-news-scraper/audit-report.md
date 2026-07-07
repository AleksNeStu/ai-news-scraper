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

### Perceivable

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 1 | **MAJOR** | 1.1.1 Non-text Content | `apps/web/src/app/page.tsx` | `StatCard` icon-only quick-action cards rely on `aria-label`; one card (`Total articles`) wraps a Lucide icon without alt-equivalent text. Manual review required — automated axe will flag the unlabeled `<svg>`. | Source review |
| 2 | **MINOR** | 1.3.1 Info and Relationships | `apps/web/src/components/layout/AppHeader.tsx:34-50` | `NavLink` components are anchors but the parent `<nav>` does not declare `aria-label="Primary"`. Multiple `<nav>` regions would fail the "bypass blocks" rule when more than one is added. | Source review |
| 3 | **MINOR** | 1.4.3 Contrast (Minimum) | Tailwind v4 dark theme | Dark theme relies on `text-muted-foreground` over `bg-canvas`. The exact contrast ratio depends on the final token values (configured in `apps/web/src/app/globals.css`). **Automated scanner will report precise violations** — verify after design tokens are finalized. | Pending token audit |
| 4 | **MINOR** | 1.4.11 Non-text Contrast | UI controls (focus rings, button borders) | Tailwind v4 default focus rings may not meet the 3:1 non-text contrast requirement against dark backgrounds. Apply `outline` / `box-shadow` overrides. | Source review |
| 5 | **MINOR** | 1.4.12 Text Spacing | Global | `globals.css` does not enforce a min line-height or paragraph spacing that survives user stylesheet overrides. WCAG 1.4.12 requires content to remain usable when users override line-height to 1.5×, paragraph spacing to 2×, etc. | Source review |

### Operable

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 6 | **MAJOR** | 2.1.1 Keyboard | `apps/web/src/components/NotificationBell.tsx` | The notification dropdown opens on click; the keyboard equivalent (`Enter` / `Space` to toggle) is not exercised in tests. If the toggle is a `<div>` with onClick (vs a `<button>`), axe will flag it as "non-interactive element with interactive handler". | Source review |
| 7 | **MAJOR** | 2.4.1 Bypass Blocks | `apps/web/src/app/layout.tsx` | No skip-link in the root layout. WCAG 2.4.1 requires a mechanism to bypass repeated navigation. The `<header>` + `<nav>` repeat on every page; a "Skip to main content" link is the canonical fix. | Source review |
| 8 | **MAJOR** | 2.4.3 Focus Order | `apps/web/src/components/auth/LogoutButton.tsx` | Logout button has a "Logging out…" pending state with `aria-busy`. Focus management during the transition needs a manual pass — if focus stays on a now-disabled button, screen readers may stall. | Manual required |
| 9 | **MAJOR** | 2.4.7 Focus Visible | Global | `globals.css` does not declare a `:focus-visible` rule. Browsers apply their default (often faint) outline on dark themes; the project's `headline-serif` / design tokens need an explicit override. | Source review |
| 10 | **MAJOR** | 2.5.3 Label in Name | `apps/web/src/app/(app)/scrape/page.tsx` | Buttons containing only icons (e.g. "Submit URL" via `ArrowRight`) need an accessible name that matches their visible label per WCAG 2.5.3. Voice-control users say "click submit" — the button's accessible name must contain "submit". | Source review |
| 11 | **MINOR** | 2.5.8 Target Size (Minimum) | WCAG 2.2 — 24×24px | Nav links in `AppHeader.tsx` use `px-3 py-1.5` with `text-sm` — the bounding box of each link is roughly 32-40px tall but may be narrower than 24px on mobile wrapping. Automated check via axe 2.5.8 tag. | Pending scan |

### Understandable

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 12 | **MINOR** | 3.3.1 Error Identification | `apps/web/src/app/(auth)/register/page.tsx` | Recently hardened in Task #36 — `parsePydanticFieldErrors` extracts per-field messages and surfaces them inline. Manual verification that the error container has `role="alert"` (or `aria-live="polite"`) required. | Manual required |
| 13 | **MINOR** | 3.3.7 Redundant Entry | WCAG 2.2 — info the user already provided | `/register` does not pre-fill email if the user returns to it; not a blocker for MVP but worth tracking. | Source review |

### Robust

| # | Severity | WCAG | Location | Finding | Source |
|---|---|---|---|---|---|
| 14 | **MINOR** | 4.1.2 Name, Role, Value | Various | Lucide icons render as `<svg>` with `aria-hidden` correctly when decorative. **Manual check**: search results + dashboard cards should be reviewed for SVGs that are NOT decorative (e.g. status indicators) but lack `role="img"` + `<title>`. | Source review |

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
| MAJOR | 7 (Phase 1 + Phase 3 combined) |
| MINOR | 7 |
| Pending manual pass | 6 (Phase 2 + 2.2-specific) |
| Pass (no action) | 2 (2.5.7, 2.6.1) |

## Remediation plan (atomic commits, sequential)

The fix commits will land in this order — each one ships a discrete
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

After fixes land, re-run the automated spec and re-execute
`manual-checklist.md`. A clean Phase 1 scan + completed Phase 2 checklist
+ sign-off on the WCAG 2.2 specific items flips this report from
"In progress" to "Passing AA".

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
