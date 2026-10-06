import * as Sentry from '@sentry/react'
import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, useLocation } from 'react-router-dom'
import App from './App'
import { LoginScreen } from './components/auth/LoginScreen'
import { AuthProvider, useAuth } from './lib/auth'
import { HealthProvider } from './lib/health'
import { PrivacyPage } from './pages/legal/PrivacyPage'
import { TermsPage } from './pages/legal/TermsPage'
import { initSentry } from './lib/sentry'
import { SyncOnOpenProvider } from './lib/syncOnOpen'
import { ThemeProvider } from './lib/theme'
import { ToastProvider } from './lib/toast'
import './index.css'

initSentry()

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element #root not found')
}

/** Legal pages must be reachable from the login screen, i.e. before auth
 * status is known or while locked out — so this check runs ahead of
 * AuthGate, not inside the routed <App> (which only renders once authed). */
function PublicRoutes({ children }: { children: ReactNode }) {
  const location = useLocation()
  if (location.pathname === '/legal/terms') return <TermsPage />
  if (location.pathname === '/legal/privacy') return <PrivacyPage />
  return <>{children}</>
}

/** Blocks the app until auth status is known; shows the passphrase gate when locked. */
function AuthGate({ children }: { children: ReactNode }) {
  const { state } = useAuth()
  if (state === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[var(--color-background)] text-sm text-muted">
        Loading…
      </div>
    )
  }
  if (state === 'locked' || state === 'pending') return <LoginScreen />
  return <>{children}</>
}

/** A render crash anywhere below here used to white-screen the whole app
 * with no recovery path. This reports it to Sentry (when configured) and
 * offers a reload instead of leaving the tab dead. */
function CrashFallback({ resetError }: { resetError: () => void }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[var(--color-background)] px-4 text-center">
      <p className="text-sm font-semibold text-primary">Something went wrong.</p>
      <p className="max-w-sm text-xs text-muted">
        TradeLogger hit an unexpected error. Your data is unaffected — try reloading.
      </p>
      <button
        type="button"
        onClick={() => {
          resetError()
          window.location.reload()
        }}
        className="rounded-xl px-4 py-2 text-sm font-semibold shadow-lg"
        style={{ background: 'var(--tl-gradient-primary)', color: 'var(--tl-gradient-ink)' }}
      >
        Reload
      </button>
    </div>
  )
}

createRoot(rootElement).render(
  <StrictMode>
    <Sentry.ErrorBoundary fallback={CrashFallback}>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <PublicRoutes>
              <AuthGate>
                <SyncOnOpenProvider>
                  <HealthProvider>
                    <ToastProvider>
                      <App />
                    </ToastProvider>
                  </HealthProvider>
                </SyncOnOpenProvider>
              </AuthGate>
            </PublicRoutes>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
)

// Register the PWA service worker in production builds only (the Vite dev server
// doesn't serve /sw.js and a SW would only get in the way of HMR).
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      /* offline shell is a progressive enhancement — ignore registration errors */
    })
  })
}
