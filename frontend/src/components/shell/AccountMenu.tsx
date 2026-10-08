import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../lib/auth'
import { useHealth } from '../../lib/health'
import { apiStatusView } from '../../lib/status'
import { useTheme } from '../../lib/theme'
import { setSoundEnabled, useSoundEnabled } from '../../lib/sound'
import { APP_VERSION } from '../../lib/appMeta'
import { LogoutIcon, MonitorIcon, MoonIcon, SoundIcon, SunIcon } from '../../lib/icons'

function initials(email: string | undefined, name: string | null | undefined): string {
  const src = (name || email || '').trim()
  if (!src) return '•'
  const parts = src.split(/[\s@._-]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (name && parts[1] ? parts[1][0] : '')).toUpperCase() || '•'
}

/**
 * The avatar menu in the top bar: who you're signed in as, appearance
 * (theme + sounds), connection status, and sign out — tucked away instead of
 * sitting in the header. Signing out used to be "click your email", which was
 * easy to hit by accident; it now lives at the bottom of this menu.
 */
export function AccountMenu() {
  const { state: authState, user, logout } = useAuth()
  const { choice, setChoice } = useTheme()
  const sound = useSoundEnabled()
  const { state: health } = useHealth()
  const api = apiStatusView(health)
  const [open, setOpen] = useState(false)
  const wrap = useRef<HTMLDivElement>(null)
  const menuId = useId()

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const healthy = api.tone === 'positive'

  return (
    <div ref={wrap} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label="Account and settings"
        className="relative grid h-9 w-9 place-items-center rounded-full border border-border bg-surface-elevated text-[12px] font-extrabold text-accent hover:bg-surface-hover"
      >
        {initials(user?.email, user?.display_name)}
        <span
          className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-background ${healthy ? 'bg-positive' : api.tone === 'negative' ? 'bg-negative' : 'bg-warning'}`}
          aria-hidden="true"
        />
      </button>

      {open ? (
        <div
          id={menuId}
          role="menu"
          aria-label="Account"
          className="tl-pop-in absolute right-0 top-[calc(100%+8px)] z-50 w-72 rounded-[var(--tl-radius-lg)] border border-border bg-surface p-1.5 shadow-[var(--tl-shadow-pop)]"
        >
          {authState === 'authed' && user ? (
            <div className="px-2.5 pb-2 pt-1.5">
              <p className="truncate text-sm font-bold text-primary">{user.display_name || 'Signed in'}</p>
              <p className="truncate text-xs text-muted">{user.email}</p>
            </div>
          ) : null}

          <div className="border-t border-border-subtle px-2.5 py-2.5">
            <p className="mb-1.5 text-[11px] font-bold uppercase tracking-[0.12em] text-muted">Appearance</p>
            <div className="tl-seg w-full" role="radiogroup" aria-label="Theme">
              {(
                [
                  ['system', 'Auto', MonitorIcon],
                  ['light', 'Light', SunIcon],
                  ['dark', 'Dark', MoonIcon],
                ] as const
              ).map(([value, label, Icon]) => (
                <button key={value} type="button" role="radio" aria-checked={choice === value} onClick={() => setChoice(value)} className="flex-1">
                  <Icon className="h-3.5 w-3.5" />
                  {label}
                </button>
              ))}
            </div>
            <button
              type="button"
              role="menuitemcheckbox"
              aria-checked={sound}
              onClick={() => setSoundEnabled(!sound)}
              className="mt-2 flex h-9 w-full items-center justify-between rounded-[var(--tl-radius)] px-2 text-sm font-semibold text-secondary hover:bg-surface-elevated hover:text-primary"
            >
              <span className="flex items-center gap-2">
                <SoundIcon muted={!sound} className="h-4 w-4" />
                Click sounds
              </span>
              <span className={`relative h-5 w-9 rounded-full transition-colors ${sound ? 'bg-accent-fill' : 'bg-surface-hover'}`} aria-hidden="true">
                <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-[left] ${sound ? 'left-[18px]' : 'left-0.5'}`} />
              </span>
            </button>
          </div>

          <div className="border-t border-border-subtle px-2.5 py-2">
            <Link to="/operations/system" role="menuitem" onClick={() => setOpen(false)} className="flex items-center justify-between rounded-[var(--tl-radius)] py-1.5 text-sm text-secondary hover:text-primary">
              <span className="flex items-center gap-2">
                <span className={`h-2 w-2 rounded-full ${healthy ? 'bg-positive' : api.tone === 'negative' ? 'bg-negative' : 'bg-warning'}`} aria-hidden="true" />
                {healthy ? 'Everything is working' : api.tone === 'negative' ? 'Can’t reach the server' : 'Checking connection…'}
              </span>
              <span className="font-mono text-[11px] text-muted">v{APP_VERSION}</span>
            </Link>
          </div>

          {authState === 'authed' ? (
            <div className="border-t border-border-subtle p-1">
              <button
                type="button"
                role="menuitem"
                onClick={() => void logout()}
                className="flex h-9 w-full items-center gap-2 rounded-[var(--tl-radius)] px-2 text-sm font-semibold text-secondary hover:bg-surface-elevated hover:text-negative"
              >
                <LogoutIcon className="h-4 w-4" />
                Sign out
              </button>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
