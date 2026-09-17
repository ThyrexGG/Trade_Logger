// Runs inside the page's own renderer context -- so a fetch() here carries
// the same session cookie the logged-in page already has, unlike a request
// made from the main process (which has no browser session at all). That's
// the only reason this file exists: to read /api/alerts as the signed-in
// user and hand the triggered count to main.js over IPC, so main.js can put
// a badge on the taskbar icon without needing to fake authentication itself.
const { ipcRenderer } = require('electron')

const ALERTS_URL = 'https://tradelogger-api.onrender.com/api/alerts'
const POLL_INTERVAL_MS = 60_000

async function pollTriggeredAlerts() {
  try {
    const res = await fetch(ALERTS_URL, { credentials: 'include' })
    if (!res.ok) return // not logged in yet, or a transient error -- just skip this tick
    const data = await res.json()
    ipcRenderer.send('tradelogger:triggered-alerts', Number(data.triggered) || 0)
  } catch {
    // offline or backend down -- the health-check notification already covers that
  }
}

window.addEventListener('DOMContentLoaded', () => {
  pollTriggeredAlerts()
  setInterval(pollTriggeredAlerts, POLL_INTERVAL_MS)
})
