# Regression prevention — ai-news-scraper

**Purpose.** The classic a11y failure: a big push fixes hundreds of
issues, then six months later half regress (someone swaps a semantic
`<button>` for a styled `<div>`, placeholder-only labels creep back).
This doc captures the **layered defenses** that keep the audit
"Passing AA" state stable as the codebase evolves.

## Layered defenses

The setup mirrors the audit-report.md's three-phase model. Each layer
catches a different class of regression; together they prevent both
silent a11y rot AND new violations at PR time.

### Layer 1 — Automated CI gate (the build-time floor)

`.github/workflows/a11y.yml` runs `@axe-core/playwright` against 13
representative templates on every PR. Severity-gated:

- **`serious` + `critical` violations** = build fails.
- **`moderate` + `minor` violations** = logged as warnings; the
  operator triages on the next manual pass.

The spec lives at `apps/web/e2e/a11y.spec.ts` and covers these
representative templates (all locale-prefixed per `next-intl`
`localePrefix: 'as-needed'`; the bare paths shown in earlier
revisions of this table resolve to the same templates via the
middleware rewrite):

| Route | Why representative |
|---|---|
| `/en/login` | Public auth form + 429 cooldown timer. |
| `/en/register` | Public registration form + 422 mass-assignment surfacing. |
| `/en/unsubscribe` | One-click unsubscribe (RFC 8058) — public-facing. |
| `/en` | Home page (top-pick + recent articles, AppHeader + skip-link). |
| `/en/dashboard` | Tiered dashboard (must-read hero + recommended / worth-a-look). |
| `/en/articles` | List view + filter toolbar. |
| `/en/articles/123` | Article detail — dynamic segment, exercises the route shell. |
| `/en/search` | Search results + filter state. |
| `/en/scrape` | URL paste + result — authenticated flow. |
| `/en/dashboard/brief` | Authenticated digest list. |
| `/en/dashboard/brief/2026-01-15` | Digest detail — dynamic date segment. |
| `/en/feeds` | Authenticated RSS subscriptions view. |
| `/en/settings` | Authenticated user settings. |

Each spec runs `AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa',
'wcag21a', 'wcag21aa', 'wcag22aa']).analyze()` and asserts zero
violations. The `wcag22aa` tag pulls in 2.5.8 (Target Size) which is
the only reliably-automatable new-in-2.2 criterion.

### Layer 2 — ESLint jsx-a11y (the dev-time floor)

`apps/web/.eslintrc.json` extends `plugin:jsx-a11y/recommended`. This
catches at edit time:

- `click-events-have-key-events` — div/span with onClick but no
  keyboard handler (catches the NotificationBell anti-pattern).
- `anchor-is-valid` — `<a href="#">` or missing href (catches
  no-link pseudo-buttons).
- `alt-text` — missing alt on `<img>` (catches finding #1 class).
- `interactive-supports-focus` — interactive role without tabindex.
- `label-has-associated-control` — `<label>` not associated with an
  input.

These are the high-volume rules. Operators can extend with
`plugin:jsx-a11y/strict` once the recommended set is clean across
the codebase.

### Layer 3 — Manual pass cadence

`manual-checklist.md` is the operator-runnable Phase 2 + Phase 3
artifact. Cadence:

- **Before each public launch** (every minor / major version).
- **Quarterly**, scheduled in the operator's calendar.
- **After any major UI rewrite** (e.g. design system overhaul).

A "manual pass complete" event updates the `audit-report.md`
headline + the per-finding severity to "Closed".

### Layer 4 — Agent / AI coding guidance

When a teammate (Agent, Cursor, or any coding assistant) generates
new UI code in this repo, the following a11y rules are non-negotiable:

1. **Semantic HTML first, ARIA second.** Reach for a real
   `<button>`, `<nav>`, `<main>`, `<label>` before adding ARIA.
   Bad ARIA is worse than none.
2. **Every interactive element is a `<button>` or `<a>`.** Never
   `<div onClick={...}>` or `<span role="button">` (the latter is a
   code smell that almost always means the role is wrong).
3. **Every `<img>` has `alt=""` (decorative) or `alt="<purpose>"`
   (functional).** Never bare `alt="image"` or `alt="photo"`.
4. **Every form field has a programmatic label.** Use `<label for>`,
   not placeholder-only.
5. **Every route has a unique `<h1>`.** Never multiple `<h1>`s; never
   skip heading levels.
6. **Status changes use `aria-live` or `role="status"`.** Loading
   spinners, cooldown timers, success / error toasts — all must be
   announced.
7. **Focus management on route change.** After a programmatic
   redirect (e.g. after successful login), move focus to the new
   page's `<h1>`.
8. **Color is not the only signal.** Status indicators use colour +
   text or icon.

These rules live in the agent brief template (see
`.claude/templates/agents/web.md` if added; otherwise inline in each
spawn). The CI gate catches them at PR time if the agent misses one.

### Layer 5 — Accessibility statement + VPAT refresh

`accessibility-statement.md` and `vpat.md` are the public-facing
artifacts. Refresh cadence:

- **Statement**: update on conformance status changes (any CRITICAL /
  MAJOR fix merged).
- **VPAT**: refresh quarterly alongside the manual pass.

## Operational checklist (per release)

Before tagging a release:

1. PR-time: axe-core scan passes (Layer 1).
2. PR-time: jsx-a11y lint clean (Layer 2).
3. Quarterly-or-launch: manual checklist executed (Layer 3).
4. Quarterly-or-launch: VPAT refreshed if any MAJOR / CRITICAL changed
   (Layer 5).
5. Statement updated to reflect new status.

## Failure mode: what to do when a regression lands

If the CI gate catches a new violation on a PR:

1. The PR cannot merge until the violation is fixed (severity
   `serious` or `critical`).
2. For `moderate` or `minor` violations: the reviewer decides —
   either fix in this PR or file a follow-up issue tagged `a11y`.
3. For regressions caught by the manual pass: file a new finding in
   `audit-report.md` with WCAG criterion + repro steps + severity.
   The fix follows the same atomic-commit pattern as the original
   remediation plan.

## Anti-patterns to flag in code review

| Pattern | Why it fails | Fix |
|---|---|---|
| `<div onClick={handler}>` | Not keyboard accessible. | Use `<button type="button" onClick={handler}>`. |
| `<a href="#" onClick={...}>` | Causes scroll-to-top; not a real link. | Use `<button>` if it's an action; use `<Link>` if it's navigation. |
| `<img>` without `alt` | Screen readers announce filename. | Add `alt=""` (decorative) or `alt="<purpose>"`. |
| Placeholder-only label | Placeholder disappears on input. | Use `<label for>` outside the input. |
| `aria-label` on a `<div>` | Divs aren't focusable. | Use `<button aria-label="...">` instead. |
| `role="button"` on a non-`<button>` | Browser / AT quirks. | Use the actual `<button>` element. |
| Skipped heading levels (`<h1>` → `<h3>`) | Screen-reader outline broken. | Use sequential levels. |
| `tabindex="1"` or higher | Disrupts natural tab order. | Use `tabindex="0"` (focusable) or `tabindex="-1"` (programmatic focus only). |
| `onClick` without `onKeyDown` / `onKeyUp` | Mouse-only handler. | Add keyboard equivalent or switch to `<button>`. |
| Auto-playing video / animation | Vestibular trigger. | Pause-on-hover or remove. |

## Cross-references

- `audit-report.md` — current findings + remediation plan.
- `manual-checklist.md` — operator-runnable Phase 2 + Phase 3 passes.
- `accessibility-statement.md` — public EAA statement.
- `vpat.md` — procurement artifact.
- `apps/web/e2e/a11y.spec.ts` — Playwright axe-core spec (always-on gate).
- `.github/workflows/a11y.yml` — runs the spec on every PR.
