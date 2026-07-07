# Manual a11y checklist — ai-news-scraper

**Purpose.** The automated axe-core scan (Phase 1) catches ~30–40% of
WCAG criteria by issue volume. The remaining 60–70% — focus order,
screen-reader announcement of state changes, link context, reflow under
user zoom — needs human eyes. **This checklist is the operator-runnable
artifact that completes the audit.**

**When to run.** Before flipping the audit-report.md header to
"Passing AA" — i.e. before the public launch that includes the EU/EEA
market. Repeat quarterly OR after any major UI rewrite, whichever
comes first.

**Tools needed.**
- **NVDA** (free, Windows) OR **VoiceOver** (free, macOS / iOS).
- **Chrome + Lighthouse** (free) for the spot-check reflow + contrast
  passes.
- **A real keyboard.** No mouse.
- **Zoom** (Ctrl/Cmd +) at 200% and 400%.

**Sign-off block** (paste at the bottom when complete, dated +
operator initials):
```
Manual pass: YYYY-MM-DD
Operator:    <name>
NVDA version:<version> / VoiceOver version: <version>
Browser:     <Chrome 124 / Firefox 127 / Safari 17.5 / ...>
Routes tested: <list>
Result:      PASS / FAIL (failures documented inline)
```

---

## Pre-flight (10 min)

- [ ] Confirm the latest `dev` build is deployed to staging
      (`https://staging.<domain>`) OR `pnpm dev` is running locally
      on `localhost:3000`.
- [ ] Clear cookies; visit `/` to land as a logged-out user. Note:
      the dashboard redirects to `/login` if auth is required —
      test both states.
- [ ] Open the route list below in a separate tab so you can tick
      rows as you go.

---

## Phase 2.A — Keyboard-only traversal (45 min)

For every route in the audit-report.md "Routes in scope" table:

### Keyboard basics
- [ ] **Tab** through the entire page from top to bottom.
- [ ] **Shift+Tab** walks back the same path in reverse (focus order
      is symmetric).
- [ ] Focus indicator is **always visible** (sufficient contrast
      against the background — see WCAG 1.4.11 / 2.4.12 in the audit
      report's findings #4, #9, #15, #17).
- [ ] No **focus traps** — Esc returns to document, no "stuck"
      modal loop.
- [ ] **Skip-link** is the first focusable element; activating it
      jumps focus to `<main>` (WCAG 2.4.1, finding #7).

### Skip-link target
- [ ] After activating the skip-link, focus is on `<main>` or the
      first heading inside it.
- [ ] **Screen-reader users** hear the page title or `<h1>` after
      the skip-link activates — verify with NVDA / VoiceOver.

### Forms
- [ ] Tab order: email → password → submit (login/register).
- [ ] **Labels** are programmatically associated (`<label for>` or
      `aria-labelledby`). Visible label text matches the
      accessible name (WCAG 2.5.3, finding #10).
- [ ] **Error messages** are announced on submit — verify with the
      screen reader (the WCAG 3.3.1 check, finding #12).
- [ ] **Cooldown timer** (login 429 UX, Task #36) is announced as
      it decrements; submit button is `aria-disabled` until the
      timer reaches 0; focus management does not trap the user.

### Modals / overlays
- [ ] NotificationBell dropdown: opens on Enter, closes on Esc,
      focus moves into the dropdown, returns to the trigger on
      close (WCAG 4.1.2, finding #6).

### Navigation
- [ ] `<nav>` has a unique `aria-label` so screen-reader users can
      distinguish header nav from any other nav region
      (finding #2).
- [ ] Nav links have visible text (icon + label), not icon-only.

### Per-route custom checks

| Route | Custom keyboard check |
|---|---|
| `/scrape` | After submit, focus moves to the result area OR stays on the submit button with an `aria-live` announcement. |
| `/search` | Filter / sort controls reachable by Tab. Results re-announced when filter changes. |
| `/unsubscribe` | Email input is focused on mount. Confirm button submits without keyboard trap. |
| `/dashboard/brief` | "Skip to brief" or in-page anchor if the brief is long. |

---

## Phase 2.B — Screen-reader pass (60 min)

Use **NVDA** (Windows) or **VoiceOver** (macOS / iOS). For each route:

- [ ] Navigate by **landmarks** (`D` in NVDA, VO+U in VoiceOver).
      Every page should expose: `<header>`, `<nav>` (with label),
      `<main>`, `<footer>` (if present).
- [ ] Navigate by **headings** (`H` in NVDA, VO+Cmd+H). Headings
      form a coherent outline (h1 → h2 → h3, no skipped levels).
- [ ] Navigate by **links** (`K` in NVDA). Link text makes sense
      out of context — no "click here", no "read more" without a
      qualifier.
- [ ] Navigate by **form controls** (`F` in NVDA). Each control has
      a programmatic label; required fields are announced.
- [ ] Navigate by **buttons** (`B` in NVDA). Icon-only buttons have
      an accessible name.
- [ ] **Status messages** (login 429 cooldown, search results loading,
      scrape success/failure) are announced via `aria-live="polite"`
      or `role="status"`.
- [ ] **Logout flow** (Task #36): the "Logging out…" state and the
      success/error transitions are announced.

### Specific screen-reader exercises

| Route | Exercise | Expected |
|---|---|---|
| `/login` | Submit empty form | All required fields announced; focus moves to first error. |
| `/login` | Submit wrong password 11 times | 11th attempt → 429 announced; cooldown timer announced. |
| `/register` | Submit with extra field | `extra_forbidden` error announced per field. |
| `/articles` | Filter to a category | Result count announced. |
| `/unsubscribe` | Tab through the form | Email input focused; submit reachable without trap. |

---

## Phase 2.C — Reflow + zoom (15 min)

- [ ] Set browser zoom to **200%** (Ctrl/Cmd + + + +). Page content
      reflows; no horizontal scroll on the `<main>` content area
      (WCAG 1.4.10). Side nav may scroll horizontally if it's a
      fixed panel — verify the page is still usable.
- [ ] Set zoom to **400%**. Verify text remains readable, no
      overlapping text, no clipped controls.
- [ ] **Set browser font size to 24px** (Chrome: Settings →
      Appearance → Font size). Verify text spacing (WCAG 1.4.12,
      finding #5) — content should remain usable.
- [ ] **Apply user stylesheet** that overrides `line-height: 1.5`,
      `letter-spacing: 0.12em`, `word-spacing: 0.16em`,
      `paragraph-spacing: 2×`. Verify content remains usable
      (WCAG 1.4.12 — all four must be tested).

---

## Phase 2.D — Context checks automation misses

- [ ] **Alt text accuracy** (WCAG 1.1.1): Lucide icons in the
      header are decorative and correctly `aria-hidden`. Any
      `<img>` or non-decorative `<svg>` should have alt text that
      describes the *function* (e.g. "Submit") not the *appearance*
      (e.g. "Arrow right icon").
- [ ] **Link purpose** (WCAG 2.4.4): No bare "click here" or
      "read more" links. Every link's accessible name + context
      tells the user where it goes.
- [ ] **Section headings** (WCAG 2.4.6): Headings describe the
      section that follows. No heading is empty.
- [ ] **Visible focus + keyboard parity** (WCAG 2.1.1, 2.4.7): Every
      mouse interaction has a keyboard equivalent.
- [ ] **Touch target size** (WCAG 2.5.8, AA in 2.2): Each
      interactive element is at least 24×24 CSS pixels (excluding
      inline links within text). Check via axe-core
      `wcag22aa` tag in the automated scan.

---

## Phase 3 — WCAG 2.2 specific (15 min)

- [ ] **Focus Not Obscured** (2.4.11): Sticky header does not
      cover the focused element when scrolling. Tab through the
      page and watch the focus ring — it must remain fully
      visible.
- [ ] **Focus Appearance** (2.4.13): Focus indicator area is at
      least 2 CSS pixels thick, contrast ≥ 3:1 against adjacent
      background. Measure with browser devtools.
- [ ] **Target Size** (2.5.8): Already checked in Phase 2.D.
- [ ] **Accessible Authentication** (3.3.8): Confirm login/register
      do not rely on cognitive function tests (no CAPTCHA, no
      security questions, no "type the characters you see").
      Password is acceptable. Passkeys are a future-work item.
- [ ] **Consistent Help** (2.6.1): N/A — the app does not yet
      provide help links. Re-evaluate if help is added.
- [ ] **Redundant Entry** (3.3.7): Pre-fill email if returning to
      `/register`. Tracked as finding #13 (MINOR).

---

## Recording results

When the manual pass completes, paste the sign-off block at the top
of this file (replacing the empty template), and update the
`audit-report.md` headline + the WCAG 2.2 specific rows with "Closed"
or "Verified manually YYYY-MM-DD".

If any check fails, write a new finding in `audit-report.md` with:
- WCAG criterion
- Reproduction steps (the route + the action that triggered the issue)
- The screen-reader output that revealed it (NVDA / VoiceOver
  transcript snippet)
- The proposed fix (semantic HTML preferred over ARIA)
- Severity (CRITICAL / MAJOR / MINOR)
- Owner (the next fix commit's author)

**Do not declare "Passing AA"** until every CRITICAL and MAJOR finding
in `audit-report.md` has a fix commit + a re-run green.
