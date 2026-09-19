/** Mirrors api/schemas.py JournalScreenshotMeta / JournalScreenshotsResponse. */
export interface JournalScreenshotMeta {
  id: string
  trade_id: string
  filename: string | null
  mime: string
  byte_size: number
  caption: string | null
  created_at: string
  url: string
}

export interface JournalScreenshotsResponse {
  trade_id: string
  screenshots: JournalScreenshotMeta[]
  timestamp: string
}
