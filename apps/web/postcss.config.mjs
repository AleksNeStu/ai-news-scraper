/**
 * PostCSS config — wires the Tailwind 4 PostCSS plugin for Next.js.
 *
 * Without this file the ``@import 'tailwindcss';`` line at the top of
 * ``src/app/globals.css`` is passed through unchanged: the resulting
 * stylesheet contains only the ``@theme`` block (CSS variables) and
 * zero utility-class definitions, so every page renders unstyled
 * (Tailwind utilities like ``flex``, ``bg-background``, ``text-foreground``
 * etc. are missing from the bundle). Adding this file activates the
 * @tailwindcss/postcss plugin which scans the project source for
 * utility usage and emits the corresponding rules.
 *
 * Tailwind 4 + Next.js 15 canonical setup per
 * https://tailwindcss.com/docs/installation/framework-guides/nextjs
 */

const config = {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}

export default config
