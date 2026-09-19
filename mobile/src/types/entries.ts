/** Mirrors api/schemas.py JournalEntry — free-standing ideas / reviews / plans (not tied to a trade). */
export type EntryKind = 'idea' | 'review' | 'observation' | 'plan'

export interface JournalEntry {
  id: string
  kind: EntryKind
  instrument: string | null
  title: string | null
  body: string
  tags: string[]
  screenshot_count: number
  created_at: string
  updated_at: string
}

export interface JournalEntryInput {
  kind?: EntryKind
  instrument?: string | null
  title?: string | null
  body?: string
  tags?: string[]
}
