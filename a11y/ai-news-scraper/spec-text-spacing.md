# Spec — Task #27 #5 Text Spacing (WCAG 1.4.12)

Status: Approved for Frontend implementation 2026-07-11
WCAG criterion: 1.4.12 Text Spacing (Level AA)
Audit finding: #5 in `a11y/ai-news-scraper/audit-report.md` (line 54)
Target file: `apps/web/src/app/globals.css`

---

## 1. One-line summary

WCAG 1.4.12 is **NOT** token-blocked; this fix can land **without** waiting
for design-token finalisation. Only #3 (1.4.3 contrast) and #4 (1.4.11
non-text contrast) are token-gated — #5 is pure CSS.

---

## 2. CSS values to apply

| Property | Selector scope | Value | Rationale |
|----------|---------------|-------|-----------|
| `line-height` | `:where(html, body, p, li, dd, td, blockquote, pre)` | `1.5` | WCAG 1.4.12: survives user override to at least 1.5× without loss of content or functionality. Unitless number inherits the element's font-size, so it scales correctly per element. |
| `margin-block-end` | `:where(p, li, dd)` | `2em` | WCAG 1.4.12: paragraphs and list items survive user override to at least 2× font-size. `em` keeps it proportional when the user bumps font-size. |

**Scope decisions (per WCAG 1.4.12):**

- **`line-height`** — applied at `html, body` for inherited default, and
  repeated on `p, li, dd, td, blockquote, pre` so these elements keep 1.5×
  even if a child element sets its own leading (the inheritance is then
  bypassed). `td` included because data tables need readable cell text.
- **`margin-block-end`** — applied to `p, li, dd` (the elements WCAG calls
  "paragraphs"). `td` is **not** included because table cells use padding,
  not paragraph spacing. Blockquote spacing is inherited from paragraph
  margin rule.
- **`<input>` and `<button>`** — **excluded** from `line-height`. Forcing
  line-height on form controls breaks the vertical centering of icon-only
  buttons and single-line inputs.
- **`<h1>`–`<h6>`** — **excluded** from `line-height`. The exclusion is
  safe under WCAG 1.4.12 regardless (the criterion only requires that
  paragraph spacing survive overrides). The rationale for the exclusion
  in our codebase is **visual**: display type wants tighter leading than
  body. In practice, headings in this codebase lack an explicit
  `leading-*` Tailwind utility (e.g. `headline-serif text-3xl` on
  `apps/web/src/app/[locale]/(app)/articles/[id]/page.tsx:113`) and
  inherit the body's `1.5` from `html`. That inherited `1.5` is still
  WCAG-conformant — if a tighter display is desired later, add
  `leading-tight` to the `headline-serif` utility class globally so the
  rule stays in one place.
- **`article` and sectioning roots** — not targeted; spacing is inherited
  via the paragraph rule.

## 3. Selector strategy: `:where()` zero-specificity

```css
@layer base {
  :where(html, body, p, li, dd, td, blockquote, pre) {
    line-height: 1.5;
  }
  :where(p, li, dd) {
    margin-block-end: 2em;
  }
}
```

**Justification:**

- **`:where()` zeros specificity** (CSS Selectors L4). This is the W3C's
  recommended pattern for "author-origin defaults that users can override"
  per the WCAG 1.4.12 Understanding document. A user stylesheet using
  normal selectors (specificity ≥ 1) overrides these rules cleanly.
- **`!important` is NOT used** because user stylesheets SHOULD be able to
  win without `!important`. The W3C note about `!important` is a fallback
  for assistive-technology override scenarios, not the default path.
- **Unlayered CSS variables are NOT used** for the paragraph spacing
  because WCAG 1.4.12 measures the *effective* spacing, and a CSS var
  only swaps the value if the user redefines the var. A direct property
  rule with `:where()` is more predictable in the `lint` + `stylelint`
  audit chain.

## 4. Layer placement: `@layer base`

Place the new rule inside the existing `@layer base { ... }` block at
`apps/web/src/app/globals.css:104-112`. Reasons:

- **Utilities can still override it.** Any `@layer utilities` rule (e.g.
  a `text-pretty` or `leading-tight` utility class) wins over `@layer
  base` — matching Tailwind v4's cascade expectations.
- **Token-driven utilities stay intact.** The `--color-*` tokens defined
  in `@theme inline` are unrelated to layout; placing the spacing rule
  in `@layer base` keeps the typography system decoupled from the token
  system (so #5 can ship before #3/#4 are finalised).
- **Focus-visible rule co-locates.** The new rule sits next to the
  existing `:focus-visible` rule in the same `@layer base` block, so
  global a11y concerns stay grouped for future audits.

## 5. Risk callouts for Frontend

1. **Form controls** — do not extend the `:where(...)` list to include
   `input`, `select`, `button`, `textarea`. Forcing `line-height: 1.5`
   on them breaks vertical centering of icon buttons (e.g. the `Plus`
   icon on `/scrape`, the `Bell` icon on the header).

2. **Heading hierarchy** — do not extend the list to `h1`–`h6`. Display
   type uses tighter `leading-tight` / `leading-snug` utilities for
   typographic balance; forcing 1.5 on headings makes article titles
   visually "loose" against body text.

3. **`p + p` selector is fragile** — do NOT use adjacent-sibling
   combinators. React / Next.js streaming inserts whitespace text nodes
   between paragraphs, so `:where(p) + :where(p)` may miss pairs in
   hydrated content. Use the unconditional bottom-margin approach: every
   paragraph gets `margin-block-end: 2em` and the **last** child
   margin is collapsed visually via the article container's
   `> *:last-child { margin-block-end: 0 }` if needed (Frontend can
   decide this is optional — WCAG allows overflow).

4. **Tailwind v4 preflight reset** — Tailwind v4's reset does NOT zero
   out `margin-block-end` on paragraphs by default (unlike v3's
   Preflight). Verify with dev tools: applying the rule should change
   the bottom margin of `<p>` from `1em` (browser default) to `2em`.
   If the user has set a *smaller* paragraph spacing, the WCAG target
   is still met because the SPEC (1.4.12) requires the rule to
   SURVIVE an override **to** 2×, not enforce it at 2×. However, having
   it at 2× by default is the safer starting point.

5. **RTL languages** — `margin-block-end` flips to the inline-start side
   in RTL contexts, which is the correct behaviour per CSS Logical
   Properties. No additional action needed.

6. **Lists inside paragraphs** — `li` gets both `line-height: 1.5` and
   `margin-block-end: 2em`. This is correct (1.4.12 covers list items)
   but may visually double-space nested lists. Frontend may add a
   scoped `:where(li > ul, li > ol) { margin-block-end: 0 }` rule if
   lint flags the visual regression.

## 6. Verification checklist (Frontend to run before commit)

- [ ] `pnpm --filter web lint` — no new CSS warnings.
- [ ] `pnpm --filter web tsc --noEmit` — no new TS errors (rule is
      pure CSS, this should pass trivially).
- [ ] Open `/articles` and `/articles/[id]` in Chrome dev tools:
      inspect a `<p>` element and confirm computed `line-height` is
      `1.5` of its font-size, computed `margin-block-end` is `2em`.
- [ ] Open `/scrape` and click the submit button. Confirm the button
      is still visually centered (not shifted up/down by line-height).
- [ ] Open `/articles/[id]` and inspect an `<h1>` or `<h2>`. Confirm
      heading line-height is **NOT** 1.5 (it should keep its
      tighter display-type leading).
- [ ] Bump browser font-size to 200% and reload `/articles`. Content
      remains readable, no horizontal scroll, no clipped text.

## 7. Commit message for Frontend to reuse

**Subject:** `fix(web,a11y): user-stylesheet-overridable text spacing (Task #27 #5)`

**Body:**

```
Closes audit-report finding #5 (WCAG 1.4.12 Text Spacing, MINOR).

Adds :where()-scoped line-height: 1.5 and margin-block-end: 2em to
paragraphs, list items, and table cells inside @layer base. The
:where() selector zeros specificity so user stylesheets override
cleanly.

Excluded from the rule: input, select, button, textarea (breaks
icon-button vertical centering) and h1–h6 (display type uses tighter
leading per the typographic scale).

This fix is independent of design-token finalisation. Token-gated
findings #3 (1.4.3) and #4 (1.4.11) remain open and are tracked
elsewhere.

Refs: a11y/ai-news-scraper/audit-report.md line 54.
Refs: a11y/ai-news-scraper/spec-text-spacing.md.
```

---

## 8. Out of scope (still owned elsewhere)

- **#3 (1.4.3 Contrast Minimum)** — Analyst / design-token owner.
- **#4 (1.4.11 Non-text Contrast)** — Analyst / design-token owner.
- **Manual NVDA / VoiceOver verification of reflow at 200%** — listed
  in `manual-checklist.md` as a Phase 2 operator task.
