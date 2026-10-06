import * as Sentry from '@sentry/react'

/**
 * Browser error monitoring — a no-op unless VITE_SENTRY_DSN is set at build
 * time (local dev and the friends-tier build are unaffected). Call once,
 * before the app renders.
 */
export function initSentry(): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return

  Sentry.init({
    dsn,
    tracesSampleRate: 0,
    beforeSend(event) {
      // The reset-password link carries a one-time token in the URL —
      // never let it reach Sentry even via a breadcrumb/request URL.
      const scrub = (url?: string) =>
        url?.includes('reset_token') ? url.replace(/reset_token=[^&]+/, 'reset_token=[scrubbed]') : url
      if (event.request?.url) event.request.url = scrub(event.request.url)
      for (const bc of event.breadcrumbs ?? []) {
        if (bc.data?.url) bc.data.url = scrub(String(bc.data.url))
      }
      return event
    },
  })
}
