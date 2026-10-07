/**
 * Plain-English translations of the codes the research engines return
 * (RISK_ON, BULLISH CONTEXT, CONFLICTING, …). The backend values stay as they
 * are — this only changes what a beginner reads. Unknown codes fall back to a
 * tidied-up version of the code itself rather than disappearing.
 */

export type Tone = 'positive' | 'negative' | 'warning' | 'neutral'

export interface Plain {
  /** a few words, e.g. "Investors are taking risks" */
  label: string
  /** one or two sentences a beginner can act on */
  explain: string
  tone: Tone
}

export function tidyCode(code: string): string {
  const s = String(code ?? '').replace(/[_-]+/g, ' ').trim().toLowerCase()
  return s ? s[0].toUpperCase() + s.slice(1) : '—'
}

const MOOD: Record<string, Plain> = {
  RISK_ON: {
    label: 'Investors are feeling confident',
    explain: 'Money is flowing into riskier things like stocks and crypto. Safe havens (gold, yen, bonds) usually lag in this mood.',
    tone: 'positive',
  },
  RISK_OFF: {
    label: 'Investors are nervous',
    explain: 'Money is moving into safe havens like gold, the yen and bonds, and away from stocks and crypto.',
    tone: 'negative',
  },
  INFLATIONARY: {
    label: 'Prices are rising faster',
    explain: 'Inflation is picking up. That tends to push interest rates up, and gold often gets attention.',
    tone: 'warning',
  },
  DISINFLATIONARY: {
    label: 'Price rises are cooling',
    explain: 'Inflation is easing, which can let central banks relax and is often good for stocks.',
    tone: 'positive',
  },
  GROWTH_ACCELERATION: {
    label: 'The economy is speeding up',
    explain: 'Growth data is getting stronger, which usually supports stocks and growth-linked currencies.',
    tone: 'positive',
  },
  GROWTH_DECELERATION: {
    label: 'The economy is slowing down',
    explain: 'Growth data is getting weaker. Traders often turn more careful and favour safer assets.',
    tone: 'negative',
  },
  USD_STRENGTH: {
    label: 'The US dollar is strong',
    explain: 'When the dollar is strong, pairs like EURUSD and GBPUSD and gold (XAUUSD) tend to fall, while USDJPY tends to rise.',
    tone: 'warning',
  },
  USD_WEAKNESS: {
    label: 'The US dollar is weak',
    explain: 'When the dollar is weak, pairs like EURUSD and GBPUSD and gold (XAUUSD) tend to rise, while USDJPY tends to fall.',
    tone: 'warning',
  },
  RATE_RISE: {
    label: 'Interest rates are heading up',
    explain: 'Higher rates usually strengthen that country’s currency and weigh on gold and stocks.',
    tone: 'warning',
  },
  RATE_FALL: {
    label: 'Interest rates are heading down',
    explain: 'Lower rates usually weaken that country’s currency and help gold and stocks.',
    tone: 'warning',
  },
  MIXED_REGIME: {
    label: 'No clear mood',
    explain: 'The signals disagree with each other. Markets like this are often choppy, so be extra careful.',
    tone: 'neutral',
  },
  INSUFFICIENT_DATA: {
    label: 'Not enough data yet',
    explain: 'There isn’t enough fresh data to judge the mood right now.',
    tone: 'neutral',
  },
}

export function marketMood(code: string): Plain {
  return MOOD[String(code).toUpperCase()] ?? { label: tidyCode(code), explain: '', tone: 'neutral' }
}

const LEAN: Record<string, Plain> = {
  'BULLISH CONTEXT': { label: 'Leaning up', explain: 'Most of the background factors point higher.', tone: 'positive' },
  'BEARISH CONTEXT': { label: 'Leaning down', explain: 'Most of the background factors point lower.', tone: 'negative' },
  NEUTRAL: { label: 'No clear lean', explain: 'The factors roughly cancel out.', tone: 'neutral' },
  MIXED: { label: 'Slight lean, not convincing', explain: 'There is a small tilt, but not a strong one.', tone: 'neutral' },
  DIVERGING: { label: 'Signals disagree', explain: 'Some factors point up and others down — usually a time to stand aside.', tone: 'warning' },
  'INSUFFICIENT DATA': { label: 'Not enough data', explain: 'Too little fresh data to say anything useful.', tone: 'neutral' },
}

/** A market's overall lean (the scanner's `context_state`). */
export function marketLean(code: string): Plain {
  return LEAN[String(code).toUpperCase().replace(/_/g, ' ')] ?? { label: tidyCode(code), explain: '', tone: 'neutral' }
}

const AGREEMENT: Record<string, Plain> = {
  ALIGNED: { label: 'Factors agree', explain: 'The different reasons all point the same way.', tone: 'positive' },
  MIXED: { label: 'Factors partly agree', explain: 'Some reasons agree, some don’t.', tone: 'neutral' },
  CONFLICTING: { label: 'Factors disagree', explain: 'The reasons point in opposite directions.', tone: 'warning' },
}

export function factorAgreement(code: string): Plain {
  return AGREEMENT[String(code).toUpperCase()] ?? { label: tidyCode(code), explain: '', tone: 'neutral' }
}

const DRIVER_WORDS: [RegExp, string][] = [
  [/dollar|usd|yield/i, 'the US dollar and interest rates'],
  [/inflation|cpi|pce/i, 'inflation news'],
  [/growth|gdp|pmi/i, 'economic growth news'],
  [/macro/i, 'the economic backdrop'],
  [/regime/i, 'the overall market mood'],
  [/cot|positioning|sentiment/i, 'what big traders are betting on'],
  [/season/i, 'what usually happens at this time of year'],
  [/session|liquidity/i, 'the trading session and volume'],
  [/smc|technical|trend|structure/i, 'the price chart itself'],
]

/** "Dollar & Cross-Asset Yields" -> "the US dollar and interest rates". */
export function driverInPlainWords(name: string): string {
  if (!name || name.toUpperCase() === 'NONE') return 'no single factor'
  for (const [re, words] of DRIVER_WORDS) if (re.test(name)) return words
  return name.toLowerCase()
}

/** The backend's USD state label is not populated (always "NEUTRAL"), so read the score instead. */
export function usdFromScore(score: number): Plain {
  if (score >= 30) return { label: 'strong', explain: 'US economic data has been beating expectations.', tone: 'warning' }
  if (score >= 10) return { label: 'a little strong', explain: 'US data has been slightly better than expected.', tone: 'neutral' }
  if (score <= -30) return { label: 'weak', explain: 'US economic data has been missing expectations.', tone: 'warning' }
  if (score <= -10) return { label: 'a little weak', explain: 'US data has been slightly worse than expected.', tone: 'neutral' }
  return { label: 'steady', explain: 'US data has been roughly in line with expectations.', tone: 'neutral' }
}

const ASSET_NAMES: Record<string, string> = {
  XAUUSD: 'Gold',
  XAGUSD: 'Silver',
  EURUSD: 'Euro vs US dollar',
  GBPUSD: 'British pound vs US dollar',
  USDJPY: 'US dollar vs Japanese yen',
  AUDUSD: 'Australian dollar vs US dollar',
  NZDUSD: 'New Zealand dollar vs US dollar',
  USDCAD: 'US dollar vs Canadian dollar',
  USDCHF: 'US dollar vs Swiss franc',
  BTCUSD: 'Bitcoin',
  ETHUSD: 'Ethereum',
  NAS100: 'US tech stocks (Nasdaq 100)',
  NDX100: 'US tech stocks (Nasdaq 100)',
  US500: 'US stocks (S&P 500)',
  SPX500: 'US stocks (S&P 500)',
  US30: 'US stocks (Dow Jones)',
  WTI: 'Oil',
  DXY: 'US dollar index',
  UKOIL: 'Brent oil',
  GER40: 'German stocks (DAX)',
  UK100: 'UK stocks (FTSE 100)',
  JP225: 'Japanese stocks (Nikkei)',
  AUDJPY: 'Australian dollar vs Japanese yen',
  EURJPY: 'Euro vs Japanese yen',
  GBPJPY: 'British pound vs Japanese yen',
  EURGBP: 'Euro vs British pound',
  SOLUSD: 'Solana',
  XRPUSD: 'XRP',
  USOIL: 'Oil',
}

/** "XAUUSD" -> "Gold"; unknown symbols return null so callers can show just the ticker. */
export function assetName(symbol: string): string | null {
  return ASSET_NAMES[String(symbol).toUpperCase()] ?? null
}
