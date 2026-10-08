import { useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { installClickSounds } from '../../lib/sound'
import { BottomNav } from './BottomNav'
import { CommandPalette } from './CommandPalette'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

/**
 * Persistent application shell: sidebar + top bar + routed content, plus the
 * phone bottom bar. Owns the mobile drawer and the command palette (Ctrl/Cmd+K).
 *
 * The ground is a plain solid page now: the old fixed glow blobs existed to
 * give frosted-glass panels something to blur, and the panels are solid.
 */
export function AppShell() {
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [paletteOpen, setPaletteOpen] = useState(false)

  useEffect(() => installClickSounds(), [])

  // Global shortcuts: Ctrl/Cmd+K toggles the palette; Escape closes overlays.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((v) => !v)
      } else if (e.key === 'Escape') {
        setPaletteOpen(false)
        setSidebarOpen(false)
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

      <div className="relative z-10 flex min-h-screen flex-col lg:pl-[var(--tl-sidebar-width)]">
        <TopBar onOpenCommandPalette={() => setPaletteOpen(true)} />

        <main id="main-content" className="flex-1 pb-[calc(4.5rem+env(safe-area-inset-bottom))] lg:pb-10">
          {/* Keyed by pathname (not full location) so it replays on a real page
              change but not on a same-page filter/query update. */}
          <div key={location.pathname} className="tl-page-in">
            <Outlet />
          </div>
        </main>
      </div>

      <BottomNav onOpenMore={() => setSidebarOpen(true)} />
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  )
}
