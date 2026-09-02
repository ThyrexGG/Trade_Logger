import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { APP_VERSION } from '../../lib/appMeta'
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

  // Global shortcut: Ctrl/Cmd+K toggles the palette.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
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
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded focus:bg-surface-elevated focus:px-3 focus:py-2 focus:text-sm focus:text-primary"
      >
        Skip to content
      </a>

      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      <div className="flex min-h-screen flex-col lg:pl-[var(--tl-sidebar-width)]">
        <TopBar
          onOpenSidebar={() => setSidebarOpen(true)}
          onOpenCommandPalette={() => setPaletteOpen(true)}
        />

        <main id="main-content" className="flex-1">
          <Outlet />
        </main>

        <footer className="border-t border-border-subtle bg-surface px-4 py-2.5 text-xs text-muted sm:px-6">
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

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
