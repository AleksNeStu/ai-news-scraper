# Accessibility statement — ai-news-scraper

**Effective date:** 2026-07-11
**Operator:** AleksNeStu (private operator; repo at
`github.com/AleksNeStu/ai-news-scraper`).
**Conformance target:** WCAG 2.1 AA (legal floor under EN 301 549
v3.2.1, the harmonised standard referenced by the European Accessibility
Act) + WCAG 2.2 AA (de-facto build target; 9 new criteria included
where applicable to the product).

> **Legal scope.** This statement addresses the European Accessibility
> Act (Directive (EU) 2019/882, **in force since 28 June 2025** for new
> products/services). It is not legal advice. Operators in scope should
> coordinate with counsel to confirm jurisdiction-specific requirements
> (Member State transpositions vary; the harmonised standard referenced
> is EN 301 549 v3.2.1).

## What this product is

AI News Search is a web application that lets users paste article URLs,
generates a personal semantic news library, and surfaces results via
full-text + vector search. The product has a public marketing site,
authenticated user dashboard, and one-click email unsubscribe (RFC 8058
compliant).

The product is **in scope** for the EAA when offered to EU consumers.
The dashboard / search / scrape flows are in scope. The marketing site,
login, register, and unsubscribe pages are in scope. Backend APIs are
out of scope as accessibility subjects (a11y is a client concern); API
error shapes are documented separately in the API's
`.agent/adr/010-exception-hierarchy.md`.

## Conformance status

**Partial — actively working toward full AA conformance.** As of
2026-07-11:

| Area | Status | Notes |
|---|---|---|
| Semantic HTML structure | Pass | `<html lang>`, `<header>`, `<nav>`, `<main>`, `<section>`, `<h1>`–`<h6>` used per template. |
| Form labels | Pass | Every input has a programmatic label. |
| Keyboard navigation | Partial | Phase 2 manual pass in progress; see `manual-checklist.md`. |
| Focus indicators | Pass | `:focus-visible` rule confirmed in `globals.css` (2px primary ring, 2px offset). |
| Skip-link | Pass | `<a href="#main">` ships as first focusable in the app-group layout. |
| Color contrast | Pending — design tokens | Depends on final design tokens in `globals.css` (finding #3). |
| Screen-reader announcement of state changes | Pass | Login cooldown timer + scrape status use `aria-live`. |
| Accessible authentication | Pass (AA) | No CAPTCHA / cognitive function tests (WCAG 3.3.8). Passkeys are a future-work item. |
| Text spacing (1.4.12) | Pass | `:where()`-scoped `line-height` + `margin-block-end` shipped in `globals.css` (Frontend commit landed 2026-07-11); Phase 2.C manual override-survival sign-off still required. |
| Consistent Help (2.6.1) | N/A | App does not yet provide help links. |

## Known limitations

The current build has these accessibility gaps, listed in priority
order. Full remediation plan and per-finding repro steps are in
`audit-report.md`.

1. **No skip-link in the root layout** (WCAG 2.4.1) — **Pass**.
   `<a href="#main">` ships as the first focusable element in
   `apps/web/src/app/[locale]/(app)/layout.tsx`, targeting
   `<main id="main" tabIndex={-1}>` (Frontend commit landed 2026-07-08).
2. **Default `:focus-visible` indicator is faint on the dark theme**
   (WCAG 2.4.7, 2.4.11, 2.4.13) — **Pass**. Explicit `:focus-visible`
   rule shipped in `apps/web/src/app/globals.css` using the cyan
   primary token at 2px outline + 2px offset (Frontend commit landed
   2026-07-08).
3. **NotificationBell uses a non-button toggle** (WCAG 4.1.2,
   finding #6) — **Pass (closed 2026-07-08)**. The trigger is now a
   native `<button type="button" aria-haspopup="menu">` with
   `aria-expanded` + `aria-controls` linking it to `id="notif-popover"`.
4. **Some icon-only buttons may not satisfy Label in Name** (WCAG
   2.5.3, finding #10) — **Pass (closed 2026-07-08)**. The audit's
   candidate cases (`/scrape`, `/search`, `/feeds` submit buttons)
   all render visible text alongside the icon; the accessible name
   matches the visible string.
5. **Color contrast under audit** (WCAG 1.4.3, finding #3) —
   **Pending — depends on final design tokens** (deferred to next
   sprint). The dark theme uses `text-muted-foreground` against
   `bg-canvas`; the ratio is not yet measured against the final token
   values.

## How we test

- **Automated CI gate** (`.github/workflows/a11y.yml` + `apps/web/e2e/a11y.spec.ts`):
  Playwright + `@axe-core/playwright` scans representative templates
  on every PR. Severity-gated: `serious` and `critical` violations
  block the PR; `minor` violations are logged for triage.
- **Lint** (`apps/web/.eslintrc.json` + `eslint-plugin-jsx-a11y`):
  Catches anchor-ambiguous-text, missing alt, click-handlers on
  non-interactive elements, etc. as a dev-time floor.
- **Manual pass** (`manual-checklist.md`): operator-runnable keyboard
  + screen-reader + reflow checklist, executed before launch and
  quarterly thereafter. The automated floor is NOT considered
  sufficient on its own.

## Feedback

If you encounter an accessibility barrier on this product, please
open an issue at `github.com/AleksNeStu/ai-news-scraper/issues` with
the label `a11y`. Include:

- The route you were on.
- The action you were trying to perform.
- The assistive technology you were using (NVDA / VoiceOver / keyboard
  only / zoom level / etc.).
- What you expected to happen vs what happened.

We aim to respond within **5 business days** and to ship a fix or
workaround within **30 calendar days** for barriers that block core
user journeys (CRITICAL severity).

## Enforcement

This statement is required under the EAA and under the equivalent
national transpositions (Germany BFSG, France, etc.). The operator
will:

1. Re-run the manual checklist quarterly.
2. Update this statement when conformance status changes.
3. Maintain the audit-report.md as the single source of truth for
   per-criterion findings.
4. Coordinate with `nest-legal-docs` for jurisdiction-specific updates
   when EN 301 549 is revised.

## Versioning

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-07-07 | Initial statement; conformance is partial, automated floor + manual checklist in place. |
| 0.2 | 2026-07-11 | Code-fixable findings closed (skip-link, focus indicators, NotificationBell keyboard parity, Label in Name candidates); conformance status table + Known limitations updated to reflect sprint 2026-07-11. |
