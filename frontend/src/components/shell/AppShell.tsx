import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { APP_VERSION } from '../../lib/appMeta'
import { BottomNav } from './BottomNav'
import { CommandPalette } from './CommandPalette'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

/**
 * Persistent application shell: sidebar + top bar + routed content + footer.
 * Owns the mobile sidebar drawer and the command palette (Ctrl/Cmd+K).
 */
export function AppShell() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

  // Global shortcuts: Ctrl/Cmd+K toggles the palette; Escape closes it
  // regardless of which element holds focus.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      } else if (e.key === 'Escape') {
        setPaletteOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  // Close transient overlays on navigation.
  useEffect(() => {
    setSidebarOpen(false)
    setPaletteOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-background">
      {/* Glassmorphism needs something under the glass to actually blur — a
         flat background gives every frosted panel nothing to show off
         against. Fixed, behind everything, ignored by input and screen
         readers. Gold + bronze + gray (`--tl-glow-*`, decorative-only
         tokens — not the app's semantic accent/info/positive colors).
         Kept deliberately subtle — a premium black-and-gold fintech card
         (the reference look) reads as mostly-black with a faint warm
         ambient glow, not a card with color visibly bleeding through it;
         gold is a rim/accent/icon color there, never a dominant wash. */}
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden="true">
        <div
          className="absolute left-[6%] top-[-10%] h-[75vh] w-[75vh] rounded-full opacity-[0.16]"
          style={{ background: 'radial-gradient(circle, var(--tl-glow-a) 0%, transparent 65%)' }}
        />
        <div
          className="absolute right-[-8%] top-[2%] h-[68vh] w-[68vh] rounded-full opacity-[0.14]"
          style={{ background: 'radial-gradient(circle, var(--tl-glow-b) 0%, transparent 65%)' }}
        />
        <div
          className="absolute bottom-[-18%] left-[28%] h-[72vh] w-[72vh] rounded-full opacity-[0.1]"
          style={{ background: 'radial-gradient(circle, var(--tl-glow-c) 0%, transparent 65%)' }}
        />
      </div>

      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface-elevated focus:px-3 focus:py-2 focus:text-sm focus:text-primary"
      >
        Skip to content
      </a>

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* `relative` (not just a later sibling) — the glow layer is `position:
         fixed`, which paints above plain in-flow content regardless of DOM
         order unless this is positioned too. */}
      <div className="relative z-10 flex min-h-screen flex-col lg:pl-[var(--tl-sidebar-width)]">
        <TopBar
          onOpenSidebar={() => setSidebarOpen(true)}
          onOpenCommandPalette={() => setPaletteOpen(true)}
        />

        <main id="main-content" className="flex-1 pb-[calc(3.5rem+env(safe-area-inset-bottom))] lg:pb-0">
          {/* Keyed by pathname (not full location) so it replays on a real page
              change but not on a same-page filter/query update. */}
          <div key={location.pathname} className="tl-page-in">
            <Outlet />
          </div>
        </main>

        <footer className="hidden border-t border-border-subtle bg-surface px-4 py-2.5 text-xs text-muted sm:px-6 lg:block">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span>
              React shell → FastAPI adapter → authoritative Python engines
            </span>
            <span className="font-mono">
              Safety: <span className="text-negative">BLOCKED</span> · v
              {APP_VERSION}
            </span>
          </div>
        </footer>
      </div>

      <BottomNav />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
