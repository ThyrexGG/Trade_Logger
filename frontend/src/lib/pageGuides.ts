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
  '/workspace/loss-limits': {
    title: 'Set a "stop for the day" rule so one bad day can’t wreck your account.',
    steps: [
      'Daily loss limit: how much you’re allowed to lose in one day before you stop trading.',
      'Drawdown limit: how far your account may fall from its highest point in total.',
      'You get a notification as you get close and when you hit a limit. It never closes trades for you.',
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
  '/workspace/chart-analyzer': {
    title: 'Get a second opinion on a chart before you trade it.',
    steps: [
      'Upload a screenshot of your chart, or paste a TradingView link.',
      'It reads your entry, stop loss and target, works out the risk-to-reward, and rates the setup.',
      'Save it to your Journal to compare the plan with what actually happened later.',
    ],
  },
  '/workspace/killzone-scanner': {
    title: 'Find a specific setup during the busiest trading hours.',
    body: 'The "killzones" are the London and New York sessions, when big moves are most likely. The scanner looks for price grabbing an obvious high or low and then turning around.',
    steps: [
      'Pick a market and run a scan; hits are marked on the chart.',
      'A hit is a candidate to study, not a buy or sell signal — tested on its own it hasn’t been profitable.',
      'Use the Plan tab to write down your entry, stop and reason before you trade.',
    ],
  },
  '/workspace/journal': {
    title: 'Your trading diary — every closed trade, plus your notes on it.',
    steps: [
      'Pick an account at the top so different accounts stay separate.',
      'Open a trade to tag the setup, rate how well you followed your plan, and add notes or a screenshot.',
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
