/**
 * The Singapore Starter API on Render. The phone talks to it directly over
 * HTTPS with a bearer token — no cookies, so none of the cross-site cookie
 * problems a WebView-style wrapper would hit.
 *
 * To test against a local API instead, start Metro with EXPO_PUBLIC_API_URL set, e.g.
 * EXPO_PUBLIC_API_URL=http://192.168.1.20:8010 npm start (phone and PC on the same Wi-Fi;
 * the Android emulator reaches the PC at http://10.0.2.2:8010).
 */
export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? 'https://tradelogger-api-sg.onrender.com'

/** Health poll cadence — matches the web pill's feel without draining battery. */
export const HEALTH_POLL_MS = 30_000

/** A request that takes longer than this is treated as unreachable. */
export const REQUEST_TIMEOUT_MS = 15_000

/** Screenshot uploads are bigger and phones are on cellular — give them longer. */
export const UPLOAD_TIMEOUT_MS = 60_000
