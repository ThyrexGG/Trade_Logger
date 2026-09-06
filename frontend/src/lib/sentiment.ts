/**
 * One place that turns any directional / verdict string the backend emits
 * (bull/bear, hawkish/dovish, beat/miss, strong/weak, tracking/diverging,
 * READY/WATCH, pass/fail, risk-on/off, …) into a consistent visual: a tone,
 * an arrow, and a plain-English word. Used by <SentimentBadge> / <SentimentText>
 * so the same idea always looks the same across the app.
 */
export type SentimentTone = 'up' | 'down' | 'flat' | 'caution'

export interface Sentiment {
  tone: SentimentTone
  /** ▲ ▼ ● ! */
  arrow: string
  /** short plain word for the tone, when the raw value is a code */
  word: string
}

const UP = /\b(BULL|BULLISH|POSITIVE|POS|BEAT|STRONG|STRONGER|IMPROV|EXPAND|HAWK|RISK.?ON|UPSIDE|CONFIRM|CONFIRMING|TRACKING|ON.?TRACK|PASS|PASSED|READY|GO|WIN|WINNING|SURVIVES|PROMISING|USABLE|FOUND|HEALTHY|OK|GOOD|GREEN|RALLY|GAIN|SUPPORT)\b/
const DOWN = /\b(BEAR|BEARISH|NEGATIVE|NEG|MISS|WEAK|WEAKER|DETERIOR|CONTRACT|DOVISH|RISK.?OFF|DOWNSIDE|DIVERG|DIVERGING|OFF.?TRACK|FAIL|FAILED|BLOCK|BLOCKED|HALT|LOSS|LOSING|REJECT|REJECTED|NOT.?ESTABLISHED|NOT.?FOUND|DECAYED|DRAG|RUIN|BAD|RED|SELL.?OFF|DROP)\b/
const CAUTION = /\b(MIXED|NEUTRAL.?HAWK|NEUTRAL.?DOV|CAUTION|WARN|WARNING|STALE|PENDING|DEGRADED|MARGINAL|INSUFFICIENT|INCONCLUSIVE|WATCH|FORMING|TENTATIVE|PARTIAL|UNCERTAIN|SHADOW|SETUP.?FORMING|NEAR.?COIN.?FLIP)\b/

const WORD: Record<SentimentTone, string> = {
  up: 'positive',
  down: 'negative',
  flat: 'neutral',
  caution: 'watch',
}
const ARROW: Record<SentimentTone, string> = {
  up: '▲',
  down: '▼',
  flat: '→',
  caution: '!',
}

/** Classify a raw string. `hint` biases a genuinely neutral value. */
export function classifySentiment(
  value: string | null | undefined,
  hint?: SentimentTone,
): Sentiment {
  const v = (value || '').toUpperCase().replace(/_/g, ' ')
  let tone: SentimentTone
  if (CAUTION.test(v) && !UP.test(v) && !DOWN.test(v)) tone = 'caution'
  else if (UP.test(v) && !DOWN.test(v)) tone = 'up'
  else if (DOWN.test(v) && !UP.test(v)) tone = 'down'
  else if (UP.test(v) && DOWN.test(v)) tone = 'caution'
  else tone = hint ?? 'flat'
  return { tone, arrow: ARROW[tone], word: WORD[tone] }
}

/** Classify a signed number (surprise, score, delta): +ve up, -ve down, 0 flat. */
export function numberSentiment(n: number | null | undefined, deadband = 0): Sentiment {
  if (n == null || !Number.isFinite(n)) return { tone: 'flat', arrow: ARROW.flat, word: WORD.flat }
  if (n > deadband) return { tone: 'up', arrow: ARROW.up, word: WORD.up }
  if (n < -deadband) return { tone: 'down', arrow: ARROW.down, word: WORD.down }
  return { tone: 'flat', arrow: ARROW.flat, word: WORD.flat }
}

/** Tailwind text-colour class for a tone. */
export function toneText(tone: SentimentTone): string {
  return tone === 'up'
    ? 'text-positive'
    : tone === 'down'
      ? 'text-negative'
      : tone === 'caution'
        ? 'text-warning'
        : 'text-muted'
}

/** Tailwind border+bg+text classes for a chip. */
export function toneChip(tone: SentimentTone): string {
  return tone === 'up'
    ? 'text-positive border-positive/30 bg-positive/10'
    : tone === 'down'
      ? 'text-negative border-negative/30 bg-negative/10'
      : tone === 'caution'
        ? 'text-warning border-warning/30 bg-warning/10'
        : 'text-secondary border-border-subtle bg-surface-elevated'
}
