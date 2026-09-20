/** Weekly performance summary (`/api/weekly-summary`): closed trades only, Monday to Sunday (UTC). */
export interface WeekDay {
  date: string
  net: number
  trades: number
}

export interface WeekTag {
  tag: string
  trades: number
  net: number
}

export interface WeekTrade {
  symbol: string
  net: number
}

export interface WeekSummary {
  trades: number
  wins: number
  losses: number
  win_rate: number | null
  net: number
  profit_factor: number | null
  best_trade: WeekTrade | null
  worst_trade: WeekTrade | null
  best_tag: WeekTag | null
  worst_tag: WeekTag | null
  /** trades this week with no setup tag */
  untagged: number
  by_day: WeekDay[]
  by_tag: WeekTag[]
}

export interface WeekBlock {
  start: string
  end: string
  key: string
  is_current: boolean
  summary: WeekSummary
}

export interface WeeklySummaryResponse {
  enabled: boolean
  weeks: WeekBlock[]
  note: string
  timestamp: string
}
