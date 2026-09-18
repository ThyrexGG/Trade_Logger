/**
 * The Singapore Starter API on Render. The phone talks to it directly over
 * HTTPS with a bearer token — no cookies, so none of the cross-site cookie
 * problems a WebView-style wrapper would hit.
 *
 * To test against a local API instead, use your PC's LAN address, e.g.
 * 'http://192.168.1.20:8010' (phone and PC on the same Wi-Fi).
 */
export const API_BASE_URL = 'https://tradelogger-api-sg.onrender.com'

/** Health poll cadence — matches the web pill's feel without draining battery. */
export const HEALTH_POLL_MS = 30_000

/** A request that takes longer than this is treated as unreachable. */
export const REQUEST_TIMEOUT_MS = 15_000
