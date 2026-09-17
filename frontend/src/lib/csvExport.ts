import type { JournalTradeItem } from '../types/operations'

/** RFC 4180 field escaping — wraps in quotes only when needed, doubles any
 * embedded quotes. Notes/setup tags can contain commas, quotes or newlines. */
function csvField(value: string | number | null | undefined): string {
  const s = value === null || value === undefined ? '' : String(value)
  if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
  return s
}

const TRADE_CSV_COLUMNS: Array<[string, (t: JournalTradeItem) => string | number | null]> = [
  ['Trade ID', (t) => t.trade_id],
  ['Account', (t) => t.account_id],
  ['Symbol', (t) => t.symbol],
  ['Direction', (t) => t.direction],
  ['Volume', (t) => t.volume],
  ['Entry Price', (t) => t.entry_price],
  ['Exit Price', (t) => t.exit_price],
  ['Commission', (t) => t.commission],
  ['Swap', (t) => t.swap],
  ['Gross Profit', (t) => t.gross_profit],
  ['Net Profit', (t) => t.net_profit],
  ['Entry Time', (t) => t.entry_time],
  ['Exit Time', (t) => t.exit_time],
  ['Duration (min)', (t) => t.duration_minutes],
  ['Setup Tag', (t) => t.setup_tag],
  ['Rating', (t) => t.rating],
  ['Notes', (t) => t.notes],
]

export function tradesToCsv(entries: JournalTradeItem[]): string {
  const header = TRADE_CSV_COLUMNS.map(([label]) => csvField(label)).join(',')
  const rows = entries.map((t) => TRADE_CSV_COLUMNS.map(([, get]) => csvField(get(t))).join(','))
  return [header, ...rows].join('\r\n')
}

/** Triggers a native save — a browser download dialog, or in the desktop
 * shell, Electron's own save-file dialog (it inherits the same download
 * behavior automatically, no extra wiring needed there). */
export function downloadCsv(filename: string, csvContent: string): void {
  // A leading BOM makes Excel open the UTF-8 file correctly instead of
  // mis-reading accented/currency characters as the system codepage.
  const blob = new Blob(['﻿', csvContent], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
