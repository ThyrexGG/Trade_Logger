// Runs inside the page's own renderer context -- so a fetch() here carries
// the same session cookie the logged-in page already has, unlike a request
// made from the main process (which has no browser session at all). That's
// the only reason this file exists: to read the API as the signed-in user and
// hand what it finds to main.js over IPC, so main.js can show native
// notifications / a taskbar badge without needing to fake authentication.
//
// It does two jobs:
//   1. newly triggered price alerts  -> taskbar badge (clears when you open the window)
//   2. trade opened / closed   -> native Windows notification
const { ipcRenderer } = require('electron')

// The Singapore API the site itself talks to. Keep in sync with main.js.
const API_BASE = 'https://tradelogger-api-sg.onrender.com'
const ALERTS_URL = `${API_BASE}/api/alerts`
const EVENTS_URL = `${API_BASE}/api/push/events`
const ALERT_POLL_MS = 60_000
const EVENT_POLL_MS = 30_000

async function pollTriggeredAlerts() {
  try {
    const res = await fetch(ALERTS_URL, { credentials: 'include' })
    if (!res.ok) return // not logged in yet, or a transient error -- just skip this tick
    const data = await res.json()
    // When each triggered alert fired (ms). main.js badges only the ones you have not seen.
    const stamps = (data.alerts || []).filter((a) => a.status === 'TRIGGERED').map((a) => Date.parse(a.triggered_at) || 1)
    ipcRenderer.send('tradelogger:triggered-alerts', stamps)
  } catch {
    // offline or backend down -- the health-check notification already covers that
  }
}

// --- trade events -----------------------------------------------------------
// The server records every "trade opened" / "trade closed" once. We remember
// (in main.js, per TradeLogger account) the last event id we showed, so a
// restart never replays history and a fresh install starts from "now".
let userId = null
let lastEventId = null

async function fetchEvents(afterId) {
  const url = afterId == null ? EVENTS_URL : `${EVENTS_URL}?after_id=${afterId}`
  const res = await fetch(url, { credentials: 'include' })
  if (!res.ok) return null // 401 = not signed in yet; try again next tick
  return res.json()
}

async function pollTradeEvents() {
  try {
    if (lastEventId == null) {
      // Baseline call: tells us who is signed in and the newest event id.
      const base = await fetchEvents(null)
      if (!base) return
      userId = base.user_id
      const saved = await ipcRenderer.invoke('tradelogger:get-last-event-id', userId)
      if (saved == null) {
        // First time this account is seen on this PC: start from now, don't replay history.
        lastEventId = base.latest_id
        await ipcRenderer.invoke('tradelogger:set-last-event-id', userId, lastEventId)
        return
      }
      lastEventId = saved // catch up on anything that happened while the app was closed
    }
    const data = await fetchEvents(lastEventId)
    if (!data) return
    if (data.user_id && data.user_id !== userId) {
      // A different account signed in on this window -- re-baseline on the next tick.
      userId = null
      lastEventId = null
      return
    }
    if (data.events && data.events.length) {
      lastEventId = Math.max(lastEventId, ...data.events.map((e) => Number(e.id) || 0))
      await ipcRenderer.invoke('tradelogger:set-last-event-id', userId, lastEventId)
      ipcRenderer.send('tradelogger:trade-events', data.events)
    }
  } catch {
    // offline / backend down -- the health check covers that; try again next tick
  }
}

window.addEventListener('DOMContentLoaded', () => {
  pollTriggeredAlerts()
  setInterval(pollTriggeredAlerts, ALERT_POLL_MS)
  pollTradeEvents()
  setInterval(pollTradeEvents, EVENT_POLL_MS)
})
