/**
 * Bridge exposed by desktop/preload.js via contextBridge — only present when
 * the page is running inside the Electron desktop shell, and even there only
 * does real work on the owner's own dev machine (see desktop/main.js). Every
 * caller must use optional chaining; `undefined` means "not available here",
 * not a failure.
 */
interface TradeLoggerDesktopBridge {
  triggerMT5SyncNow: () => Promise<{
    ok: boolean
    skipped?: boolean
    reason?: string
    error?: string | null
  }>
}

interface Window {
  tradelogger?: TradeLoggerDesktopBridge
}
