import { StrictMode, type ReactNode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { LoginScreen } from './components/auth/LoginScreen'
import { AuthProvider, useAuth } from './lib/auth'
import { HealthProvider } from './lib/health'
import './index.css'

const rootElement = document.getElementById('root')
if (!rootElement) {
  throw new Error('Root element #root not found')
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
  if (state === 'locked') return <LoginScreen />
  return <>{children}</>
}

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <AuthGate>
          <HealthProvider>
            <App />
          </HealthProvider>
        </AuthGate>
      </AuthProvider>
    </BrowserRouter>
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
