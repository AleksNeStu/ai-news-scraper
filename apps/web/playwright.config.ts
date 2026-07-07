import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright config — drives the axe-core a11y spec.
 *
 * Tests are gated by severity inside the spec itself (see
 * ``apps/web/e2e/a11y.spec.ts``); this file just configures the
 * browser + project layout.
 *
 * The CI workflow at ``.github/workflows/a11y.yml`` builds the app
 * via ``pnpm build`` and previews with ``next start`` before invoking
 * this config. Locally you can either:
 *
 *   $ pnpm dev           # in one shell
 *   $ BASE_URL=http://localhost:3000 pnpm exec playwright test e2e/a11y.spec.ts
 */
export default defineConfig({
  testDir: './e2e',
  // Single browser for the a11y spec; expand if a11y coverage should
  // also catch platform-specific regressions (Safari VoiceOver vs
  // NVDA announcements, etc.).
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // CI-friendly defaults. Locally you may want ``--ui`` for the
  // interactive runner.
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['github']] : 'list',
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
})
