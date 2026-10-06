// TradeLogger desktop shell. Not a rewrite of the app -- this is a thin
// native wrapper around the live site (tradelogger.site) plus two things a
// browser tab can't do on its own: a system-tray presence with minimize-to-
// tray, and a background health check that raises a native OS notification
// if the backend goes down (see the "free uptime monitoring" conversation
// that led to this).
const { app, BrowserWindow, Tray, Menu, Notification, dialog, shell, ipcMain, globalShortcut, nativeImage } = require('electron')
const path = require('node:path')
const fs = require('node:fs')
const { spawn } = require('node:child_process')

const SITE_URL = 'https://tradelogger.site'
// The Singapore API the site itself talks to (Render "Starter" service). Keep
// in sync with API_BASE in preload.js.
const API_BASE = 'https://tradelogger-api-sg.onrender.com'
// /api/health only proves the process is alive and deliberately never touches the
// database, so it stays green even when Neon itself is unreachable (e.g. a
// compute-hour quota) -- exactly the case this app most needs to detect. /api/health/db
// does a real SELECT 1, so it's what actually reflects "can this app do anything".
const HEALTH_URL = `${API_BASE}/api/health/db`
const JOURNAL_URL = `${SITE_URL}/workspace/journal`
// More new trade events than this at once (e.g. the PC was off overnight) are
// collapsed into a single summary notification instead of a burst.
const MAX_INDIVIDUAL_NOTIFICATIONS = 4
const HEALTH_CHECK_INTERVAL_MS = 60_000
const HEALTH_CHECK_TIMEOUT_MS = 10_000
const ICON_PATH = path.join(__dirname, 'build', 'icon.ico')
const OVERLAY_BADGE_PATH = path.join(__dirname, 'build', 'overlay-badge.png')
const SHOW_WINDOW_SHORTCUT = 'CommandOrControl+Shift+L'

// --- local fallback (run_local_fallback.py) -------------------------------
// Only meaningful on the owner's own dev machine, where the actual project
// checkout + Python + MT5 live -- a packaged copy on anyone else's PC simply
// won't find this path and silently stays on the normal retry screen (see
// the existsSync guard in startLocalFallback). Two straight failed health
// checks (~2 min) before switching, not one -- a single blip shouldn't spin
// up a whole local server + re-sync.
const REPO_ROOT = 'C:\\Users\\Asus\\Desktop\\Trade_Logger'
const FALLBACK_SCRIPT = path.join(REPO_ROOT, 'run_local_fallback.py')
const FALLBACK_PORT = 8010
const FALLBACK_URL = `http://127.0.0.1:${FALLBACK_PORT}/`
const FALLBACK_HEALTH_URL = `http://127.0.0.1:${FALLBACK_PORT}/api/health`
const FALLBACK_FAILURE_THRESHOLD = 2
const FALLBACK_START_TIMEOUT_MS = 90_000 // --sync-now can take a while (MT5 + Capital.com history)

// --- on-demand local MT5 push (agent/mt5_push_agent.py --once) -----------
// The cloud backend (Render, Linux) can never reach this PC's MT5 terminal --
// MetaTrader5 is Windows-only -- so clicking "Sync now" while on the cloud
// normally only syncs Capital.com, and MT5 data otherwise waits for this same
// agent's 15-minute scheduled task. Same REPO_ROOT existsSync guard as the
// local fallback above: a no-op on any PC other than the owner's own dev
// checkout (a friend's install uses their own separately-scheduled agent).
const MT5_PUSH_AGENT = path.join(REPO_ROOT, 'agent', 'mt5_push_agent.py')
const MT5_SYNC_TIMEOUT_MS = 60_000
let localFallbackProcess = null
let usingLocalFallback = false
let consecutiveCloudFailures = 0

let mainWindow = null
let tray = null
let isQuitting = false
// Tracks whether the last known state was "down" so we notify once on
// failure and once on recovery, not every single poll.
let backendIsDown = false
// Alerts stay TRIGGERED on the server until deleted, so the badge counts only the ones
// fired since the window was last in front of you (compared on the server's own clock).
let lastTriggeredAlertCount = 0
let triggeredStamps = []
let alertsSeenAt = null
// Launched by "Start with Windows": stay in the tray instead of popping a window.
const startHidden = process.argv.includes('--hidden')

// --- tiny persisted state: the last trade-event id already shown, per account.
// (preload.js is sandboxed and can't touch the disk, so main owns this file.)
function statePath() {
  return path.join(app.getPath('userData'), 'state.json')
}
function readState() {
  try {
    return JSON.parse(fs.readFileSync(statePath(), 'utf8'))
  } catch {
    return {}
  }
}
function writeState(state) {
  try {
    fs.writeFileSync(statePath(), JSON.stringify(state))
  } catch {
    // read-only profile etc. -- worst case we re-baseline next launch
  }
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#0a0a0a', // matches the site's dark theme -- no white flash on load
    show: !startHidden,
    icon: ICON_PATH,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      // Lets preload.js read /api/alerts using the page's own logged-in
      // session (a fetch from the main process would have no cookies at
      // all) and report the triggered count back over IPC -- see preload.js.
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  mainWindow.loadURL(SITE_URL)

  mainWindow.on('focus', markAlertsSeen)
  mainWindow.on('show', markAlertsSeen)

  // Open anything that isn't the app itself (e.g. an affiliate link on the
  // Partners page) in the user's real browser instead of inside the shell.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(SITE_URL)) {
      shell.openExternal(url)
      return { action: 'deny' }
    }
    return { action: 'allow' }
  })

  // Closing the window minimizes to tray instead of quitting, so the
  // background health check keeps running. Quit for real via the tray menu.
  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
    }
  })
}

function showWindow() {
  if (!mainWindow) {
    createWindow()
    return
  }
  if (mainWindow.isMinimized()) mainWindow.restore()
  mainWindow.show()
  mainWindow.focus()
}

function createTray() {
  tray = new Tray(ICON_PATH)
  tray.setToolTip('TradeLogger — checking backend…')
  tray.on('click', showWindow)
  rebuildTrayMenu()
}

function rebuildTrayMenu() {
  const statusLabel = usingLocalFallback
    ? 'Backend: local fallback (cloud down)'
    : backendIsDown
      ? 'Backend: DOWN'
      : 'Backend: healthy'
  const alertsLabel =
    lastTriggeredAlertCount > 0
      ? `${lastTriggeredAlertCount} new triggered alert${lastTriggeredAlertCount === 1 ? '' : 's'}`
      : 'No new triggered alerts'
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: 'Open TradeLogger', click: showWindow },
      { label: `Show window (${SHOW_WINDOW_SHORTCUT.replace('CommandOrControl', 'Ctrl')})`, enabled: false },
      { label: statusLabel, enabled: false },
      { label: alertsLabel, enabled: false },
      { type: 'separator' },
      { label: 'Send test notification', click: sendTestNotification },
      {
        // Trade notifications only arrive while the app is running, so this is the
        // switch that makes them reliable. Only meaningful for the installed app.
        label: 'Start with Windows',
        type: 'checkbox',
        checked: app.getLoginItemSettings().openAtLogin,
        enabled: app.isPackaged,
        click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked, args: ['--hidden'] }),
      },
      { type: 'separator' },
      {
        label: 'Quit',
        click: () => {
          isQuitting = true
          app.quit()
        },
      },
    ]),
  )
}

function applyAlertBadge() {
  if (alertsSeenAt == null) alertsSeenAt = Number(readState().alertsSeenAt) || 0
  const count = triggeredStamps.filter((t) => t > alertsSeenAt).length
  lastTriggeredAlertCount = count
  if (mainWindow) {
    if (count > 0) {
      const badge = nativeImage.createFromPath(OVERLAY_BADGE_PATH)
      mainWindow.setOverlayIcon(badge, `${count} new triggered price alert${count === 1 ? '' : 's'}`)
    } else {
      mainWindow.setOverlayIcon(null, '')
    }
  }
  if (tray) rebuildTrayMenu()
}

// The window is in front of you: every alert fired so far counts as seen, and the badge clears.
function markAlertsSeen() {
  if (alertsSeenAt == null) alertsSeenAt = Number(readState().alertsSeenAt) || 0
  const latest = triggeredStamps.length ? Math.max(...triggeredStamps) : 0
  if (latest > alertsSeenAt) {
    alertsSeenAt = latest
    writeState({ ...readState(), alertsSeenAt })
  }
  applyAlertBadge()
}

function setTriggeredAlertBadge(stamps) {
  triggeredStamps = stamps
  if (mainWindow && mainWindow.isVisible() && mainWindow.isFocused()) markAlertsSeen()
  else applyAlertBadge()
}

function openJournal() {
  showWindow()
  if (mainWindow) mainWindow.loadURL(JOURNAL_URL)
}

function showTradeNotifications(events) {
  if (!events.length || !Notification.isSupported()) return
  if (events.length > MAX_INDIVIDUAL_NOTIFICATIONS) {
    const count = (kind) => events.filter((e) => e.kind === kind).length
    const parts = []
    if (count('opened')) parts.push(`${count('opened')} opened`)
    if (count('closed')) parts.push(`${count('closed')} closed`)
    if (count('alert')) parts.push(`${count('alert')} price alert${count('alert') === 1 ? '' : 's'}`)
    const n = new Notification({ title: `${events.length} trade updates`, body: parts.join(' · '), icon: ICON_PATH })
    n.on('click', openJournal)
    n.show()
    return
  }
  for (const e of events) {
    const n = new Notification({ title: String(e.title || 'TradeLogger'), body: String(e.body || ''), icon: ICON_PATH })
    n.on('click', openJournal)
    n.show()
  }
}

// Tray > "Send test notification": shows a sample trade alert through the same
// Notification path real ones use, so you can tell whether Windows displays
// them (Focus assist / Do not disturb / notification settings) without
// waiting for a real trade. Does not exercise the server feed.
function sendTestNotification() {
  const explain = (detail) =>
    dialog.showMessageBox({
      type: 'warning',
      title: 'TradeLogger',
      message: 'Windows did not accept the test notification.',
      detail,
    })
  if (!Notification.isSupported()) {
    void explain('Notifications are not supported here. Check Settings > System > Notifications.')
    return
  }
  const n = new Notification({
    title: 'Test: US500 BUY opened',
    body: 'If you can read this, trade alerts will look like this. Click it to open the Journal.',
    icon: ICON_PATH,
  })
  n.on('click', openJournal)
  n.on('failed', (_event, error) => void explain(String(error || 'Unknown error.')))
  n.show()
}

async function pingUrl(url, timeoutMs) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

async function waitForFallbackHealthy(deadline) {
  while (Date.now() < deadline) {
    if (await pingUrl(FALLBACK_HEALTH_URL, 3_000)) return true
    await new Promise((resolve) => setTimeout(resolve, 2_000))
  }
  return false
}

// After a failed attempt (script missing on this machine, python not found, sync/startup
// timed out), don't hammer a retry every single 60s poll -- back off for a while.
let nextFallbackAttemptAt = 0

function fallbackLog(msg) {
  try {
    fs.appendFileSync(path.join(app.getPath('userData'), 'fallback.log'), `[${new Date().toISOString()}] ${msg}\n`)
  } catch {
    /* best effort -- this is debugging aid, never the reason a switch fails */
  }
}

// Every python child here is spawned with shell: true, so `child` is cmd.exe --
// child.kill() ends only that wrapper and leaves python running, orphaned
// (that's how a fallback server kept polling MT5 for 11+ hours). /T takes the
// whole tree down.
function killTree(child) {
  if (!child) return
  if (process.platform === 'win32' && child.pid) {
    spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true }).on('error', () => {})
    return
  }
  try {
    child.kill()
  } catch {
    /* already gone */
  }
}

function stopLocalFallback() {
  if (localFallbackProcess) {
    killTree(localFallbackProcess)
    localFallbackProcess = null
  }
}

async function startLocalFallback() {
  if (usingLocalFallback || localFallbackProcess) return
  if (!fs.existsSync(FALLBACK_SCRIPT)) {
    // Not the owner's dev machine (or the checkout moved) -- never going to work here,
    // stop bothering to check for the rest of this run.
    fallbackLog(`SKIP: ${FALLBACK_SCRIPT} does not exist on this machine`)
    nextFallbackAttemptAt = Infinity
    return
  }

  fallbackLog('spawning local fallback server ...')
  try {
    // shell: true -- goes through cmd.exe's own PATH resolution rather than Node's,
    // which is what actually finds `python` reliably regardless of how/where this
    // app itself got launched from (Explorer, Start Menu, a scheduled task, ...).
    // --parent-pid: the server exits on its own if this app dies without
    // cleaning up (crash, force-close) -- will-quit never runs in that case.
    localFallbackProcess = spawn('python', [FALLBACK_SCRIPT, '--sync-now', '--port', String(FALLBACK_PORT), '--parent-pid', String(process.pid)], {
      cwd: REPO_ROOT,
      windowsHide: true,
      shell: true,
    })
  } catch (err) {
    fallbackLog(`spawn threw: ${err}`)
    localFallbackProcess = null
    nextFallbackAttemptAt = Date.now() + 5 * 60_000
    return
  }
  localFallbackProcess.on('exit', (code) => {
    fallbackLog(`local fallback process exited (code ${code})`)
    localFallbackProcess = null
  })
  localFallbackProcess.on('error', (err) => {
    fallbackLog(`local fallback process error: ${err}`)
    localFallbackProcess = null
  })

  const ok = await waitForFallbackHealthy(Date.now() + FALLBACK_START_TIMEOUT_MS)
  fallbackLog(`waitForFallbackHealthy -> ${ok}`)
  if (!ok) {
    stopLocalFallback()
    nextFallbackAttemptAt = Date.now() + 5 * 60_000
    return
  }

  usingLocalFallback = true
  if (mainWindow) mainWindow.loadURL(FALLBACK_URL)
  if (tray) tray.setToolTip('TradeLogger — local fallback (cloud down)')
  if (Notification.isSupported()) {
    new Notification({
      title: 'Switched to local mode',
      body: "The cloud backend is down, so TradeLogger is showing this PC's own copy of your data until it's back.",
      icon: ICON_PATH,
    }).show()
  }
  rebuildTrayMenu()
}

function runMT5PushAgentOnce() {
  return new Promise((resolve) => {
    if (!fs.existsSync(MT5_PUSH_AGENT)) {
      resolve({ ok: false, skipped: true, reason: 'not_this_machine' })
      return
    }
    let settled = false
    const finish = (result) => {
      if (settled) return
      settled = true
      resolve(result)
    }

    let child
    try {
      // shell: true for the same PATH-resolution reason as startLocalFallback.
      child = spawn('python', [MT5_PUSH_AGENT, '--once'], {
        cwd: REPO_ROOT,
        windowsHide: true,
        shell: true,
      })
    } catch (err) {
      finish({ ok: false, error: String(err) })
      return
    }

    const timer = setTimeout(() => {
      killTree(child)
      finish({ ok: false, error: 'timed out' })
    }, MT5_SYNC_TIMEOUT_MS)

    let stderr = ''
    child.stderr?.on('data', (d) => {
      stderr += String(d)
    })
    child.on('exit', (code) => {
      clearTimeout(timer)
      finish({ ok: code === 0, error: code === 0 ? null : stderr.trim().slice(-500) || `exit code ${code}` })
    })
    child.on('error', (err) => {
      clearTimeout(timer)
      finish({ ok: false, error: String(err) })
    })
  })
}

function returnToCloud() {
  stopLocalFallback()
  usingLocalFallback = false
  if (mainWindow) mainWindow.loadURL(SITE_URL)
  if (Notification.isSupported()) {
    new Notification({
      title: 'TradeLogger is back online',
      body: 'The cloud backend is responding again — switched back from local fallback mode.',
      icon: ICON_PATH,
    }).show()
  }
}

async function checkBackendHealth() {
  const healthy = await pingUrl(HEALTH_URL, HEALTH_CHECK_TIMEOUT_MS)
  consecutiveCloudFailures = healthy ? 0 : consecutiveCloudFailures + 1

  if (!healthy && !backendIsDown) {
    backendIsDown = true
    if (!usingLocalFallback) {
      tray.setToolTip('TradeLogger — backend DOWN')
      if (Notification.isSupported()) {
        new Notification({
          title: 'TradeLogger backend is down',
          body: 'The API stopped responding to health checks. It usually recovers on its own within a minute or two.',
          icon: ICON_PATH,
        }).show()
      }
    }
  } else if (healthy && backendIsDown) {
    backendIsDown = false
    if (usingLocalFallback) {
      returnToCloud()
    } else {
      tray.setToolTip('TradeLogger — healthy')
      if (Notification.isSupported()) {
        new Notification({
          title: 'TradeLogger is back up',
          body: 'The backend is responding normally again.',
          icon: ICON_PATH,
        }).show()
      }
    }
  } else if (healthy) {
    tray.setToolTip(usingLocalFallback ? 'TradeLogger — local fallback (cloud down)' : 'TradeLogger — healthy')
  }

  fallbackLog(`health check: healthy=${healthy} consecutiveFailures=${consecutiveCloudFailures}`)
  if (
    !healthy &&
    !usingLocalFallback &&
    consecutiveCloudFailures >= FALLBACK_FAILURE_THRESHOLD &&
    Date.now() >= nextFallbackAttemptAt
  ) {
    void startLocalFallback()
  }
  rebuildTrayMenu()
}

// Only one copy of the app should run at once -- a second launch just
// focuses the existing window instead of opening a duplicate.
// Same id as build.appId, so Windows attributes toasts to "TradeLogger".
// Dev runs (`electron .`) get their own id: Electron auto-creates a Start Menu
// "Electron.lnk" -> node_modules\electron.exe stamped with whatever id is set
// here, and Windows then resolved the INSTALLED app's taskbar/toast icon to
// that shortcut -- the Electron atom instead of ours.
if (process.platform === 'win32') {
  app.setAppUserModelId(app.isPackaged ? 'site.tradelogger.desktop' : 'site.tradelogger.desktop.dev')
}
const gotSingleInstanceLock = app.requestSingleInstanceLock()
if (!gotSingleInstanceLock) {
  app.quit()
} else {
  app.on('second-instance', showWindow)

  app.whenReady().then(() => {
    createWindow()
    createTray()
    checkBackendHealth()
    setInterval(checkBackendHealth, HEALTH_CHECK_INTERVAL_MS)

    // Bring the window to front from anywhere, even when it's minimized to
    // tray -- the same "quick jump to the app" pattern Slack/Discord use.
    globalShortcut.register(SHOW_WINDOW_SHORTCUT, showWindow)
  })

  // preload.js polls /api/alerts (as the logged-in user, since it runs in
  // the page's own session) and reports the triggered count here so it can
  // become a taskbar badge -- a background signal that something needs
  // attention without having to keep the window open.
  ipcMain.on('tradelogger:triggered-alerts', (_event, stamps) => {
    setTriggeredAlertBadge(Array.isArray(stamps) ? stamps.map(Number).filter(Number.isFinite) : [])
  })

  // "Sync now" in the page calls this (see useSyncControl.ts) alongside its
  // normal cloud API call, so MT5 doesn't have to wait for the scheduled task.
  ipcMain.handle('tradelogger:mt5-sync-now', () => runMT5PushAgentOnce())

  // Last trade-event id already shown, remembered per TradeLogger account so a
  // restart never replays history and switching accounts can't skip events.
  ipcMain.handle('tradelogger:get-last-event-id', (_event, userId) => {
    const id = readState().lastEventId?.[String(userId)]
    return Number.isFinite(id) ? id : null
  })
  ipcMain.handle('tradelogger:set-last-event-id', (_event, userId, eventId) => {
    const state = readState()
    state.lastEventId = { ...(state.lastEventId || {}), [String(userId)]: Number(eventId) || 0 }
    writeState(state)
  })

  // preload.js hands us new trade opened / closed events from the server.
  ipcMain.on('tradelogger:trade-events', (_event, events) => {
    showTradeNotifications(Array.isArray(events) ? events : [])
  })

  app.on('will-quit', () => {
    globalShortcut.unregisterAll()
    stopLocalFallback() // never leave the local Python server running after the app exits
  })

  app.on('window-all-closed', () => {
    // Tray-resident app: closing the window (handled above) never actually
    // triggers this, but keep the platform-conventional guard for macOS/Linux.
    if (process.platform !== 'darwin') {
      // no-op: stay alive in the tray
    }
  })

  app.on('before-quit', () => {
    isQuitting = true
  })

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
    else showWindow()
  })
}
