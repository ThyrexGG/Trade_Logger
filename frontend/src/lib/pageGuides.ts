/**
 * Beginner guides, one per page, keyed by route. <PageContainer> looks the
 * current path up here and shows it under the page title (and, when a page
 * has one, the guide replaces the old one-line technical description).
 * Written for someone new to trading: what the page is for, how to read it,
 * what to do with it.
 */

export interface GuideContent {
  title: string
  body?: string
  steps?: string[]
}

const GUIDES: Record<string, GuideContent> = {
  '/workspace/market': {
    title: 'Live prices for the markets you follow.',
    steps: [
      'Pick a market from the watchlist on the left to see its chart.',
      'Switch the chart timeframe (15m, 1h, 1D…) to zoom out or in — longer timeframes show the bigger trend.',
      'Green means the price is up today, red means it’s down.',
    ],
  },
  '/workspace/positions': {
    title: 'The trades you have open right now.',
    body: 'Floating P&L is what each trade would make or lose if you closed it this second — it keeps moving until you do.',
    steps: [
      'Check that every open trade has a stop loss (SL) so a loss can’t run away from you.',
      'You can add notes or a screenshot while the trade is running; they carry over to the Journal when it closes.',
    ],
  },
  '/workspace/risk': {
    title: 'Work out a safe trade size before you place it.',
    body: 'Enter how much of your account you’re willing to lose if the trade goes wrong and where your stop loss is — it tells you how big the trade should be.',
    steps: [
      'Most traders risk 0.5% – 1% of the account per trade. Risking more makes a losing streak much more painful.',
      'This only calculates — it never places a trade.',
    ],
  },
  '/workspace/alerts': {
    title: 'Get told when a price reaches a level you care about.',
    steps: [
      'Choose a market, a price, and whether you want to know when it goes above or below it.',
      'Alerts only notify you — they never buy or sell anything.',
    ],
  },
  '/workspace/analytics': {
    title: 'How your trading has actually gone, in numbers.',
    steps: [
      'Pick an account at the top so different accounts aren’t mixed together.',
      'Win rate is how often you win; profit factor is money won divided by money lost (above 1 means you’re making money overall).',
      'Look at which symbols and setups make or lose you the most — that’s where to focus.',
      'Click a day in the calendar to see the trades from that day.',
    ],
  },
  '/workspace/assistant': {
    title: 'Ask questions about your own trading in plain English.',
    steps: [
      'Try "How did I do this week?" or "Which symbol loses me the most money?"',
      'It reads your TradeLogger data to answer. It can’t place trades, and its answers aren’t financial advice.',
    ],
  },
  '/workspace/trade-planner': {
    title: 'Plan a trade before you take it — step by step.',
    body: 'Most beginner losses come from jumping into trades without a plan. Work left to right through the tabs.',
    steps: [
      'Find setups: scan a market for price grabbing an obvious high or low during the busiest hours (the London and New York "killzones") and then turning around. A hit is something to study, not a buy or sell signal.',
      'All my markets: run the same scan on every market you watch, side by side.',
      'Check my chart: upload a screenshot of your own chart and get your entry, stop, target, risk-to-reward and a rating.',
      'Write my plan: note your entry, stop loss, target and the reason — it saves to your Journal so you can compare it with what happened.',
    ],
  },
  '/workspace/journal': {
    title: 'Your trading diary — every closed trade, plus your notes on it.',
    steps: [
      'Pick an account at the top so different accounts stay separate.',
      'Under each trade, tap how it was: By my rules, Bent my rules, or Rushed. That one tap is all the journal needs; notes, screenshots and the rest are optional.',
      'Reviewing your journal every week is the fastest way to stop repeating the same mistakes.',
    ],
  },
  '/research/crypto-carry': {
    title: 'A low-risk way to earn a small, steady return from crypto, and how it’s been doing.',
    body: 'It means holding crypto and betting against the same crypto at once, so price moves cancel out, and collecting the regular "funding" payments traders pay each other. Think of it as a savings-style return, not a way to get rich quick.',
    steps: [
      'The verdict at the top says whether it has held up so far.',
      'The tracker below records how it does week by week from now on.',
      'This is research — nothing here trades for you.',
    ],
  },
  '/research/macro': {
    title: 'The economic news that moves currencies and gold.',
    steps: [
      'Upcoming events are big announcements (like interest-rate decisions or jobs reports) — prices often jump around them, so many traders avoid opening trades just before.',
      'A "surprise" is when a number comes out better or worse than expected — that’s what actually moves prices.',
      'Strongest/weakest currencies show whose economy has been beating expectations lately.',
    ],
  },
  '/operations/system': {
    title: 'Is everything behind the app working?',
    body: 'Green means fine. If something is red, your data may be out of date — try "Sync now", or check Connections.',
  },
  '/operations/connections': {
    title: 'Connect your broker so your trades come in automatically.',
    steps: [
      'Your login details are encrypted before they’re stored.',
      'Once connected, trades sync on their own; "Sync now" pulls the latest immediately.',
    ],
  },
  '/operations/partners': {
    title: 'Brokers and prop firms we trust.',
    body: 'Some are referral links — signing up through them may support TradeLogger at no extra cost to you.',
  },
  '/research/intelligence/asset/': {
    title: 'The full story behind one market’s lean.',
    steps: [
      'The overall score is from -100 (strongly leaning down) to +100 (strongly leaning up).',
      'Each factor (economy, positioning, the chart, the time of year) adds its own push up or down — when they agree, the lean is more trustworthy.',
      'It’s background, not a trade signal.',
    ],
  },
}

/** Exact path first, then a prefix match (for routes with a parameter, e.g. an asset page). */
export function guideForPath(pathname: string): { id: string; guide: GuideContent } | null {
  const path = pathname.replace(/\/+$/, '')
  if (GUIDES[path]) return { id: path, guide: GUIDES[path] }
  for (const key of Object.keys(GUIDES)) {
    if (key.endsWith('/') && path.startsWith(key)) return { id: key, guide: GUIDES[key] }
  }
  return null
}
