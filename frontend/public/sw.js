/*
 * TradeLogger service worker — app-shell caching for an installable PWA.
 *
 * Deliberately minimal and safe:
 *  - /api/* is NEVER touched. Data always goes to the network; there is no
 *    offline write path and stale financial data must not be served.
 *  - Navigations: network-first, fall back to the last cached document so a
 *    flaky connection still opens the app ("last seen" shell).
 *  - Static assets (Vite emits content-hashed filenames): stale-while-revalidate.
 *  - Bump CACHE to invalidate everything on a breaking change.
 */
const CACHE = 'tl-shell-v1'
const ASSET_RE = /\.(?:js|css|woff2?|png|svg|webp|ico|json|webmanifest)$/

self.addEventListener('install', (event) => {
  self.skipWaiting()
  event.waitUntil(caches.open(CACHE))
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const { request } = event
  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return
  if (url.pathname.startsWith('/api/')) return // never cache API traffic

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone()
          caches.open(CACHE).then((c) => c.put('/index.html', copy))
          return res
        })
        .catch(() => caches.match('/index.html').then((r) => r || caches.match(request))),
    )
    return
  }

  if (ASSET_RE.test(url.pathname)) {
    event.respondWith(
      caches.open(CACHE).then((cache) =>
        cache.match(request).then((cached) => {
          const network = fetch(request)
            .then((res) => {
              if (res.ok) cache.put(request, res.clone())
              return res
            })
            .catch(() => cached)
          return cached || network
        }),
      ),
    )
  }
})
