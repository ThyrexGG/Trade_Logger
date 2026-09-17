// TradeLogger desktop shell. Not a rewrite of the app -- this is a thin
// native wrapper around the live site (tradelogger.site) plus two things a
// browser tab can't do on its own: a system-tray presence with minimize-to-
// tray, and a background health check that raises a native OS notification
// if the backend goes down (see the "free uptime monitoring" conversation
// that led to this).
const { app, BrowserWindow, Tray, Menu, Notification, shell, ipcMain, globalShortcut, nativeImage } = require('electron')
const path = require('node:path')

const SITE_URL = 'https://tradelogger.site'
const HEALTH_URL = 'https://tradelogger-api.onrender.com/api/health'
const HEALTH_CHECK_INTERVAL_MS = 60_000
const HEALTH_CHECK_TIMEOUT_MS = 10_000
const ICON_PATH = path.join(__dirname, 'build', 'icon.ico')
const OVERLAY_BADGE_PATH = path.join(__dirname, 'build', 'overlay-badge.png')
const SHOW_WINDOW_SHORTCUT = 'CommandOrControl+Shift+L'

let mainWindow = null
let tray = null
let isQuitting = false
// Tracks whether the last known state was "down" so we notify once on
// failure and once on recovery, not every single poll.
let backendIsDown = false
let lastTriggeredAlertCount = 0

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: '#0a0a0a', // matches the site's dark theme -- no white flash on load
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
  const statusLabel = backendIsDown ? 'Backend: DOWN' : 'Backend: healthy'
  const alertsLabel =
    lastTriggeredAlertCount > 0
      ? `${lastTriggeredAlertCount} triggered alert${lastTriggeredAlertCount === 1 ? '' : 's'}`
      : 'No triggered alerts'
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: 'Open TradeLogger', click: showWindow },
      { label: `Show window (${SHOW_WINDOW_SHORTCUT.replace('CommandOrControl', 'Ctrl')})`, enabled: false },
      { label: statusLabel, enabled: false },
      { label: alertsLabel, enabled: false },
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

function setTriggeredAlertBadge(count) {
  lastTriggeredAlertCount = count
  if (mainWindow) {
    if (count > 0) {
      const badge = nativeImage.createFromPath(OVERLAY_BADGE_PATH)
      mainWindow.setOverlayIcon(badge, `${count} triggered price alert${count === 1 ? '' : 's'}`)
    } else {
      mainWindow.setOverlayIcon(null, '')
    }
  }
  if (tray) rebuildTrayMenu()
}

async function checkBackendHealth() {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT_MS)
  let healthy = false
  try {
    const res = await fetch(HEALTH_URL, { signal: controller.signal })
    healthy = res.ok
  } catch {
    healthy = false
  } finally {
    clearTimeout(timer)
  }

  if (!healthy && !backendIsDown) {
    backendIsDown = true
    tray.setToolTip('TradeLogger — backend DOWN')
    if (Notification.isSupported()) {
      new Notification({
        title: 'TradeLogger backend is down',
        body: 'The API stopped responding to health checks. It may recover on its own (Render free tier restarts automatically).',
        icon: ICON_PATH,
      }).show()
    }
  } else if (healthy && backendIsDown) {
    backendIsDown = false
    tray.setToolTip('TradeLogger — healthy')
    if (Notification.isSupported()) {
      new Notification({
        title: 'TradeLogger is back up',
        body: 'The backend is responding normally again.',
        icon: ICON_PATH,
      }).show()
    }
  } else if (healthy) {
    tray.setToolTip('TradeLogger — healthy')
  }
  rebuildTrayMenu()
}

// Only one copy of the app should run at once -- a second launch just
// focuses the existing window instead of opening a duplicate.
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
  ipcMain.on('tradelogger:triggered-alerts', (_event, count) => {
    setTriggeredAlertBadge(Number(count) || 0)
  })

  app.on('will-quit', () => {
    globalShortcut.unregisterAll()
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
