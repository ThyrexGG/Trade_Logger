import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { filterCommands } from '../../lib/commands'
import { EnterIcon, SearchIcon } from '../../lib/icons'

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

/**
 * Keyboard-first navigation palette. Opening/closing is owned by the shell
 * (Ctrl/Cmd+K); this component handles search, arrow navigation, Enter to
 * navigate, Escape to close, and focus management.
 */
export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const restoreFocusRef = useRef<HTMLElement | null>(null)
  const [query, setQuery] = useState('')
  const [activeIndex, setActiveIndex] = useState(0)

  const results = useMemo(() => filterCommands(query), [query])

  useEffect(() => {
    if (open) {
      restoreFocusRef.current = document.activeElement as HTMLElement | null
      setQuery('')
      setActiveIndex(0)
      // focus after paint so the element exists
      requestAnimationFrame(() => inputRef.current?.focus())
    } else {
      restoreFocusRef.current?.focus?.()
    }
  }, [open])

  useEffect(() => {
    setActiveIndex(0)
  }, [query])

  useEffect(() => {
    listRef.current
      ?.querySelector('[data-active="true"]')
      ?.scrollIntoView({ block: 'nearest' })
  }, [activeIndex])

  if (!open) return null

  const select = (index: number) => {
    const cmd = results[index]
    if (!cmd) return
    onClose()
    navigate(cmd.route)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIndex((i) => (results.length ? (i + 1) % results.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) =>
        results.length ? (i - 1 + results.length) % results.length : 0,
      )
    } else if (e.key === 'Enter') {
      e.preventDefault()
      select(activeIndex)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 px-4 pt-[12vh]"
      onMouseDown={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="w-full max-w-xl overflow-hidden rounded-lg border border-border bg-surface shadow-2xl"
        onMouseDown={(e) => e.stopPropagation()}
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-2.5 border-b border-border-subtle px-3.5">
          <SearchIcon className="h-4 w-4 shrink-0 text-muted" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search TradeLogger…"
            aria-label="Search commands"
            aria-controls="command-palette-list"
            className="w-full bg-transparent py-3 text-sm text-primary placeholder:text-muted focus:outline-none"
          />
          <kbd className="rounded bg-surface-elevated px-1.5 py-0.5 font-mono text-[10px] text-muted">
            Esc
          </kbd>
        </div>

        <ul
          ref={listRef}
          id="command-palette-list"
          role="listbox"
          aria-label="Commands"
          className="max-h-[52vh] overflow-y-auto p-1.5"
        >
          {results.length === 0 ? (
            <li className="px-3 py-6 text-center text-sm text-muted">
              No matching commands
            </li>
          ) : (
            results.map((cmd, i) => {
              const Icon = cmd.icon
              const isActive = i === activeIndex
              return (
                <li key={cmd.id} role="option" aria-selected={isActive}>
                  <button
                    type="button"
                    data-active={isActive}
                    onMouseEnter={() => setActiveIndex(i)}
                    onClick={() => select(i)}
                    className={`flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-left ${
                      isActive ? 'bg-surface-hover' : ''
                    }`}
                  >
                    <Icon
                      className={
                        isActive ? 'text-accent' : 'text-muted'
                      }
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-sm text-primary">
                        {cmd.label}
                      </span>
                      <span className="block truncate text-xs text-muted">
                        {cmd.description}
                      </span>
                    </span>
                    <span className="shrink-0 rounded bg-surface-elevated px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted">
                      {cmd.zone}
                    </span>
                    {isActive ? (
                      <EnterIcon className="h-3.5 w-3.5 shrink-0 text-muted" />
                    ) : null}
                  </button>
                </li>
              )
            })
          )}
        </ul>
      </div>
    </div>
  )
}
