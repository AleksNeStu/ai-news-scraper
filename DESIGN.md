# DESIGN.md — AI News Search

> Stack: Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · shadcn/ui (slate base, re-themed)
> Source-of-truth for: `apps/web/src/app/globals.css` (CSS vars + `@theme inline`) → Tailwind tokens → shadcn components.
> Generated via `/design-md` skill (mode: generate). Look family: news / data-dense dashboard.

---

## 1. Brand & Voice

**Mission.** Make any news reader's personal archive feel like a private intelligence desk — searchable, summarizable, sortable.

**Voice.** Calm, factual, quietly technical. No exclamation marks in UI copy. No marketing fluff in tooltips. The product's job is to remove noise, not add it.

**Mood keywords**: editorial, data-dense, dark-first, no fluff, no chrome, restrained motion.

**Anti-mood**: SaaS pastel, glassmorphism, gradient mesh, oversized hero, playful microcopy.

## 2. Color System

### Principles

- **Dark mode is primary.** The product is read at night, in tabs alongside other news. Light mode is a courtesy, not a first-class citizen.
- **One accent, used sparingly.** Electric cyan is the only "look at me" color; it appears on primary actions, active states, and numeric badges.
- **Amber, not red.** Warnings are amber (`--destructive` is misnamed; rename mentally to `--warn`). News isn't life-or-death. Error states are not aggressive.
- **Semantic over brand-named.** All tokens are `--primary`, `--surface`, `--muted` — never `--news-cyan` or `--ai-brand`.

### Palette

| Token | OKLCH | Tailwind class | Use |
|---|---|---|---|
| `--background` | `oklch(0.16 0.03 250)` | `bg-background` | Page canvas |
| `--canvas` | `oklch(0.20 0.03 250)` | `bg-canvas` | Card / panel surface |
| `--surface` | `oklch(0.26 0.03 250)` | `bg-surface` | Input / inset |
| `--border` | `oklch(0.34 0.02 250)` | `border-border` | Hairlines |
| `--foreground` | `oklch(0.94 0.02 95)` | `text-foreground` | Primary text |
| `--muted-foreground` | `oklch(0.70 0.02 250)` | `text-muted-foreground` | Secondary text |
| `--primary` | `oklch(0.78 0.16 200)` | `bg-primary text-primary` | CTA / active |
| `--secondary` | `oklch(0.55 0.10 220)` | `bg-secondary` | Subtle accent |
| `--destructive` (amber/warn) | `oklch(0.78 0.16 70)` | `text-destructive` | Warning, non-fatal error |
| `--success` | `oklch(0.72 0.18 160)` | `text-success` | Success, positive trend |

### Contrast

- Body text on background: `0.94` on `0.16` → ~12.5:1 (AAA).
- `--primary` on `--background`: ~7:1 (AAA).
- `--muted-foreground` on `--background`: ~4.7:1 (AA).

All combinations exceed WCAG 2.2 AA. Re-verify with `design-verify` after any token change.

## 3. Typography

| Role | Family | Weight | Notes |
|---|---|---|---|
| Body / UI | **Geist** (variable) | 400 / 500 / 600 | Tabular numerics on (`font-feature-settings: "tnum"`) for counts and scores |
| Code / data | **Geist Mono** | 400 | Vector dims, hashes, JSON snippets |
| Editorial accent | **Fraunces** (variable serif) | 500 / 600 | Article headlines only — calls back to newspaper tradition |

**Scale** (Tailwind defaults are fine; do not invent a custom scale):
- Display: `text-3xl` / `text-2xl` (page titles)
- Body: `text-sm` (default for everything UI; `text-base` only in article body)
- Caption: `text-xs text-muted-foreground`

**Editorial heading class**: `.headline-serif` → applies Fraunces, weight 600, letter-spacing -0.02em. Used on article titles, dashboard welcome.

## 4. Spacing & Layout

- **4px grid.** All spacing is a multiple of 4 (Tailwind default).
- **Container**: `max-w-6xl` for dashboards, `max-w-3xl` for article detail, `max-w-sm` for auth.
- **Vertical rhythm**: section gaps are `space-y-8` (32px); intra-section `space-y-3` (12px).
- **Padding**: cards `p-4` or `p-5`; auth forms `p-8`.

## 5. Components

### Inventory

| Component | shadcn base | Notes |
|---|---|---|
| Button | `button` | Primary uses `--primary`. Variants: default, ghost, outline, destructive (amber). |
| Input | `input` | Border `--border`, focus `--primary`. No floating labels. |
| Card | `card` | `--canvas` background, `--border` 1px. No shadow. |
| Badge | `badge` | Topic pills, score chips. Mono font for numeric. |
| Separator | `separator` | 1px `--border`. |
| Skeleton | custom `.skeleton` class | Shimmer animation, no shadcn primitive needed. |
| EmptyState | custom | Dashed border, centered CTA. |

### States

Every interactive component must visually distinguish: default, hover, focus, active, disabled.

- **Hover**: border lightens to `--primary` at 40% alpha, OR background shifts up one step on the surface scale.
- **Focus**: 2px `--primary` ring (Tailwind `focus-visible:ring-2`).
- **Active**: `--primary` background, `--primary-foreground` text.
- **Disabled**: 50% opacity, `cursor-not-allowed`. Never grey-out alone — opacity tells the truth.

### Anti-patterns

- ❌ No drop shadows on cards (only hairlines). The data is the content.
- ❌ No rounded corners > `--radius` (0.5rem). Larger curves look childish.
- ❌ No gradients on UI surfaces. Gradients only on data viz (heatmaps, if/when added).
- ❌ No icons > 24px inside buttons. Buttons are for words.
- ❌ No skeletons that pulse-opacity (distracting). Use translate-X shimmer instead.

## 6. Iconography

- **lucide-react** (shadcn default). Stroke 2px (default).
- Icon size: 16px (inline) / 20px (button) / 24px (nav). Never larger in UI.
- Icons are functional, not decorative. Never use icons as section headers — use words.

## 7. Motion

- **Page transitions**: 150ms ease-out on opacity only. No slide.
- **Feed-poll reveal**: items fade in with 12px translate-up, staggered 40ms, capped at 6 items.
- **Skeleton shimmer**: 1.5s linear infinite, translate-based.
- **No parallax. No spring physics. No bouncing.**
- Respect `prefers-reduced-motion: reduce` — disable all transforms.

## 8. Accessibility

- **WCAG 2.2 AA target.** All text combinations verified above.
- **Keyboard**: every interactive element focusable; visible focus ring on `--primary`.
- **Screen reader**: `<nav>`/`<main>`/`<article>` landmarks on every page.
- **Color is never the sole signal** — status badges always include text or icon.
- **Form labels**: visible, never placeholder-only.
- **Reduced motion**: always honored.

## 9. Anti-patterns (project-specific)

These are the mistakes an agent will make if it doesn't read this file:

- ❌ **Do NOT use zinc or neutral-only palettes.** This is not `ai-real-estate-assistant`. The deep navy + cyan is intentional — it differentiates the projects.
- ❌ **Do NOT round cards to 1rem or 1.5rem.** Stay at 0.5rem — sharp corners suit data.
- ❌ **Do NOT use Framer Motion for trivial hover/focus transitions.** Tailwind transitions only.
- ❌ **Do NOT call `--destructive` "danger" or paint it red.** It's amber. News is not life-or-death.
- ❌ **Do NOT use Fraunces for UI labels.** Only for article headlines (editorial accent).
- ❌ **Do NOT add emoji to buttons or empty states.** Icons via lucide only.
- ❌ **Do NOT center long-form content.** Article body uses `max-w-3xl` left-aligned.
- ❌ **Do NOT use Inter or Roboto.** Geist + Fraunces. Period.

## Stack

- next: 15+
- react: 19
- tailwindcss: 4
- shadcn-ui: latest (slate base, re-themed)
- icons: lucide-react

## Changelog

- 2026-06-28 — Initial spec generated via `/design-md` (generate mode). News/data-feel look. Deep navy + electric cyan.