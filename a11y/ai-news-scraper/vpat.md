# VPAT 2.5 — ai-news-scraper

**Product:** AI News Search (web application).
**Operator:** AleksNeStu.
**Report date:** 2026-07-11.
**Standards evaluated:**
- WCAG 2.1 Level A + AA (legal floor under EN 301 549 v3.2.1)
- WCAG 2.2 Level A + AA (de-facto build target)
- Section 508 (US federal procurement; covered by WCAG 2.1 AA
  mapping)

> **VPAT 2.5 — Voluntary Product Accessibility Template.** This is the
> industry-standard artifact for enterprise and government procurement.
> Each criterion is marked **Supports / Partially Supports / Does Not
> Support / Not Applicable / Not Evaluated** with notes. Procurement
> teams use this to evaluate fitness for their buyers.

## Summary

| Standard | Level | Result |
|---|---|---|
| WCAG 2.1 | A | Partially Supports |
| WCAG 2.1 | AA | Partially Supports |
| WCAG 2.2 | A | Partially Supports |
| WCAG 2.2 | AA | Partially Supports |
| Section 508 | — | Partially Supports (mapped to WCAG 2.1 AA) |

The product is actively working toward full conformance. The detailed
per-criterion table is below; remediation plan + per-finding repro
steps are in `audit-report.md`.

## Per-criterion table (WCAG 2.1 + 2.2 AA)

| Criterion | Name | Level | Result | Notes |
|---|---|---|---|---|
| 1.1.1 | Non-text Content | A | Partially Supports | Icon-only controls have accessible names via `aria-label`; manual review of dashboard cards pending (finding #1). |
| 1.2.1 | Audio-only and Video-only (Prerecorded) | A | N/A | Product has no audio/video content. |
| 1.2.2 | Captions (Prerecorded) | A | N/A | Product has no audio/video content. |
| 1.2.3 | Audio Description or Media Alternative (Prerecorded) | A | N/A | Product has no audio/video content. |
| 1.2.4 | Captions (Live) | AA | N/A | Product has no live audio/video content. |
| 1.2.5 | Audio Description (Prerecorded) | AA | N/A | Product has no audio/video content. |
| 1.3.1 | Info and Relationships | A | Partially Supports | Semantic HTML used in templates; nav region needs `aria-label` (finding #2). |
| 1.3.2 | Meaningful Sequence | A | Supports | DOM order matches visual order; verified by source review. |
| 1.3.3 | Sensory Characteristics | A | Supports | No instructions rely solely on shape / colour / position. |
| 1.3.4 | Orientation | AA | Supports | Layout works in portrait + landscape; no orientation lock. |
| 1.3.5 | Identify Input Purpose | AA | Partially Supports | Form fields use `type="email"` / `type="password"`; `autocomplete` attributes pending for the login form. |
| 1.4.1 | Use of Color | A | Supports | Status indicators use colour + text label or icon. |
| 1.4.2 | Audio Control | A | N/A | Product has no audio content. |
| 1.4.3 | Contrast (Minimum) | AA | **Not Evaluated** | Depends on final design tokens (finding #3); pending token audit. |
| 1.4.4 | Resize Text | AA | Supports | Text reflows up to 200% zoom without loss. |
| 1.4.5 | Images of Text | AA | Supports | No images of text used in product UI. |
| 1.4.10 | Reflow | AA | Supports | Page reflows at 320 CSS px width without horizontal scrolling on `<main>`. |
| 1.4.11 | Non-text Contrast | AA | **Not Evaluated** | UI controls + focus indicators pending token audit (finding #4). |
| 1.4.12 | Text Spacing | AA | **Not Evaluated** | Pending manual reflow pass (finding #5). |
| 1.4.13 | Content on Hover or Focus | AA | Supports | No hover-only content used. |
| 2.1.1 | Keyboard | A | Partially Supports | NotificationBell needs keyboard equivalent (finding #6). |
| 2.1.2 | No Keyboard Trap | A | Supports | No known focus traps. |
| 2.1.4 | Character Key Shortcuts | A | N/A | Product has no character key shortcuts. |
| 2.2.1 | Timing Adjustable | A | Supports | Login cooldown timer is user-visible + announced. |
| 2.2.2 | Pause, Stop, Hide | A | N/A | No auto-updating / moving content. |
| 2.3.1 | Three Flashes or Below Threshold | A | Supports | No flashing content. |
| 2.4.1 | Bypass Blocks | A | Partially Supports | Skip-link implemented in app-group layout; minor audit detail pending operator Phase 2 pass (finding #7 closed 2026-07-11). |
| 2.4.2 | Page Titled | A | Supports | `<title>` set per route via `metadata.title`. |
| 2.4.3 | Focus Order | A | Partially Supports | Source review shows order is logical; manual pass pending (finding #8). |
| 2.4.4 | Link Purpose (In Context) | A | Supports | All links have descriptive text or `aria-label`. |
| 2.4.5 | Multiple Ways | AA | Supports | Header nav + footer links + breadcrumbs across the dashboard. |
| 2.4.6 | Headings and Labels | AA | Partially Supports | Headings describe sections; some icon-only controls need explicit labels (finding #10). |
| 2.4.7 | Focus Visible | AA | Supports | `:focus-visible` rule confirmed in `globals.css` (2px primary ring, 2px offset) (finding #9 closed 2026-07-11). |
| 2.4.11 | Focus Not Obscured (Minimum) | AA (2.2) | **Not Evaluated** | Pending manual pass (Phase 3). |
| 2.4.12 | Focus Not Obscured (Enhanced) | AAA (2.2) | Not Applicable | Build target is AA. |
| 2.4.13 | Focus Appearance | AA (2.2) | **Not Evaluated** | Pending `:focus-visible` rule + manual measurement (Phase 3). |
| 2.5.1 | Pointer Gestures | A | Supports | No multi-point or path-based gestures used. |
| 2.5.2 | Pointer Cancellation | A | Supports | Click handlers fire on `mouseup` (standard browser behavior); no `mousedown` triggers. |
| 2.5.3 | Label in Name | A | Partially Supports | Manual review of icon-only controls pending (finding #10). |
| 2.5.4 | Motion Actuation | A | N/A | Product does not use motion or device tilt. |
| 2.5.7 | Dragging Movements | AA (2.2) | N/A | Product does not use drag-and-drop (verified via source review). |
| 2.5.8 | Target Size (Minimum) | AA (2.2) | Supports | Nav target size bumped via `min-h-6` on `NavLink` (Frontend commit `6edf2e0`); axe 2.5.8 tag clean on header nav region (finding #11 closed 2026-07-11). |
| 2.6.1 | Consistent Help | A (2.2) | N/A | Product does not yet provide help links. |
| 3.1.1 | Language of Page | A | Supports | `<html lang="en">` declared in root layout. |
| 3.1.2 | Language of Parts | AA | N/A | Product is English-only at present. |
| 3.2.1 | On Focus | A | Supports | Focusing an element does not trigger a context change. |
| 3.2.2 | On Input | A | Supports | Form inputs do not trigger context change without explicit submission. |
| 3.2.3 | Consistent Navigation | AA | Supports | Header nav order is consistent across authenticated routes. |
| 3.2.4 | Consistent Identification | AA | Supports | Same icons / labels used for the same functions across pages. |
| 3.2.6 | Consistent Help | A (2.2) | N/A | Same as 2.6.1. |
| 3.3.1 | Error Identification | A | Supports | Per-field errors surfaced (Task #36); `role="alert"` + `aria-live="polite"` on the inline error container confirmed via Frontend commit `5fae891` (finding #12 closed 2026-07-11). |
| 3.3.2 | Labels or Instructions | A | Supports | All form fields have labels. |
| 3.3.3 | Error Suggestion | AA | Supports | Pydantic field-level error messages surfaced verbatim per Task #36 H1 UX. |
| 3.3.4 | Error Prevention (Legal, Financial, Data) | AA | Supports | User input is stored verbatim before mutation; confirm-on-delete pattern used in settings. |
| 3.3.7 | Redundant Entry | A (2.2) | Partially Supports | `/register` email pre-filled from `sessionStorage` on return visit via Frontend commit `5fae891`; full conformance pending operator confirmation of session-based UX (finding #13 closed 2026-07-11). |
| 3.3.8 | Accessible Authentication (Minimum) | AA (2.2) | Supports | Login uses email + password only; no cognitive function tests. |
| 4.1.1 | Parsing (Removed in 2.2) | — | N/A | Criterion removed in WCAG 2.2. |
| 4.1.2 | Name, Role, Value | A | Partially Supports | Most controls correctly labelled; status SVGs given `role="img"` + `<title>` via Frontend commit `ba4311d` (finding #14 closed 2026-07-11). Remaining Lucide decorative-icon audit is partial; NotificationBell closed via finding #6. |
| 4.1.3 | Status Messages | AA | Supports | Login cooldown + scrape status + search results use `aria-live` or `role="status"`. |

## Result key

- **Supports** — the criterion is fully met across the product.
- **Partially Supports** — the criterion is met in some contexts; one
  or more findings in `audit-report.md` document the gaps.
- **Does Not Support** — the criterion is not met; a fix commit is in
  progress.
- **Not Applicable** — the criterion does not apply to this product.
- **Not Evaluated** — the criterion has not been measured yet; a manual
  pass is required (see `manual-checklist.md`).

## How to use this VPAT

Procurement teams: this VPAT is the operator's self-attestation as of
the report date. To get an updated version, request a refreshed VPAT
from the operator with the latest conformance status. The
`audit-report.md` and `manual-checklist.md` are the supporting
artifacts.

Operators: update this VPAT after every conformance-relevant change.
The recommended cadence is quarterly alongside the manual a11y pass
(see `regression-setup.md`).

**v0.2 (2026-07-11)** — Code-fixable findings closed: 2.4.1 (Bypass Blocks)
-> Partially Supports; 2.4.7 (Focus Visible) -> Supports; 2.5.8
(Target Size) -> Supports; 3.3.1 (Error Identification) -> Supports;
3.3.7 (Redundant Entry) -> Partially Supports; 4.1.2 (Name, Role, Value)
kept at Partially Supports (Lucide decorative-icon audit still partial).
Contrast (1.4.3), Non-text Contrast (1.4.11), and Text Spacing (1.4.12)
left as `Not Evaluated` — design-token-dependent per `audit-report.md`
findings #3-#5.
