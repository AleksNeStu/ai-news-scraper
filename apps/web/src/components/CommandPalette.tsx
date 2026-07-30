'use client'

/**
 * Header command palette (Task #55).
 *
 * Cmd-K / Ctrl-K opens a modal with a single search input. Pressing Enter
 * navigates to `/search?q=<query>`. Esc / backdrop click close. The palette
 * is a pure navigation launcher — the destination `/search` page runs the
 * actual search, so no loading state, results list, or quick-action
 * shortcuts live here.
 *
 * Accessibility:
 *   - `CommandDialog` wraps `Dialog` (Radix), so `role=dialog`,
 *     `aria-modal=true`, focus trap, initial focus, and return-focus-on-close
 *     are inherited from Radix and not reimplemented here.
 *   - A visually hidden `DialogTitle` is rendered so Radix's
 *     `aria-labelledby` resolves to a real string (the Radix runtime
 *     warns otherwise). The input is labeled via `aria-label` for
 *     screen-reader users.
 *   - The trigger button exposes `aria-keyshortcuts="Meta+K Control+K"` and
 *     a localized `aria-label` so screen readers announce both the action
 *     and the keyboard combo.
 *   - The Cmd-K global listener is a discoverability convenience, not the
 *     only way to open the palette — the visible button keeps it
 *     keyboard/mouse/at-only reachable.
 *
 * i18n:
 *   - All visible strings live under `Header.palette.*` (en + ru).
 *
 * Routing:
 *   - Submit uses the wrapped `useRouter` from `@/i18n/navigation`, so the
 *     locale prefix is preserved automatically (en → bare `/search`,
 *     ru → `/ru/search`).
 */

import { useEffect, useRef, useState } from 'react'
import { useRouter } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import { Search } from 'lucide-react'
import { DialogTitle } from '@/components/ui/dialog'
import { CommandDialog, CommandEmpty, CommandInput, CommandList } from '@/components/ui/command'

export function CommandPalette() {
  const t = useTranslations('Header.palette')
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const router = useRouter()
  // Mirror `open` in a ref so the keydown listener (registered once)
  // can read the current value without re-binding. setState updater
  // functions must stay pure — side effects like preventDefault belong
  // here, not inside the updater.
  const openRef = useRef(open)
  openRef.current = open

  // Global Cmd-K / Ctrl-K listener. When the palette is closed we ignore
  // keydowns that originated in a page-level editable element (so Cmd-K
  // inside another widget doesn't hijack focus). When the palette is open
  // we always honor Cmd-K so it acts as a toggle — even if focus is in
  // our own search input.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key.toLowerCase() !== 'k') return
      if (!(e.metaKey || e.ctrlKey)) return
      if (openRef.current) {
        e.preventDefault()
        setOpen(false)
        return
      }
      const target = e.target as HTMLElement | null
      if (target && (target.isContentEditable || isEditableInput(target))) return
      e.preventDefault()
      setOpen(true)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  // Reset the query whenever the palette closes so a re-open starts empty.
  useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const q = query.trim()
    if (!q) return
    setOpen(false)
    router.push({ pathname: '/search', query: { q } })
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t('openLabel')}
        aria-keyshortcuts="Meta+K Control+K"
        data-testid="command-palette-trigger"
        className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-surface px-3 text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground"
      >
        <Search className="h-4 w-4" aria-hidden="true" />
        <span className="hidden sm:inline">{t('placeholder')}</span>
        <kbd
          aria-hidden="true"
          className="hidden rounded border border-border bg-canvas px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground sm:inline"
        >
          {t('kbdHint')}
        </kbd>
      </button>

      <CommandDialog open={open} onOpenChange={setOpen}>
        <DialogTitle className="sr-only">{t('openTitle')}</DialogTitle>
        <form onSubmit={onSubmit}>
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder={t('searchPlaceholder')}
            aria-label={t('searchPlaceholder')}
            data-testid="command-palette-input"
          />
          <CommandList>
            <CommandEmpty>{t('emptyHint')}</CommandEmpty>
          </CommandList>
        </form>
      </CommandDialog>
    </>
  )
}

function isEditableInput(el: HTMLElement): boolean {
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}
