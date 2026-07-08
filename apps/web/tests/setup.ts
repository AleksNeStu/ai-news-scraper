import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// Radix UI primitives (Popover, Select, Tooltip) call ResizeObserver
// during layout. jsdom doesn't ship it; polyfill a no-op so the
// components can mount in tests.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
}

// cmdk calls `el.scrollIntoView({ block: 'nearest' })` on the active
// option when the list is rendered; jsdom doesn't implement it. cmdk
// guards the call, but a no-op keeps the tests deterministic.
if (!HTMLElement.prototype.scrollIntoView) {
  HTMLElement.prototype.scrollIntoView = function () {}
}

afterEach(() => {
  cleanup()
})
