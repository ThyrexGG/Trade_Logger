import { useEffect, useMemo, useState } from 'react'
import type {
  BacktestMode,
  BacktestRunRequest,
  StrategyLabResponse,
} from '../../types/research'
import { LabeledField, inputClass, SegmentedControl } from '../risk/fields'
import { SectionCard } from './primitives'
import { parseNumberInput } from '../../lib/format'

interface Props {
  lab: StrategyLabResponse
  initialSymbol?: string | null
  running: boolean
  onRun: (req: BacktestRunRequest) => void
  onConfigChange: (req: BacktestRunRequest | null) => void
}

type NumKey =
  | 'capital'
  | 'risk_pct'
  | 'sl_atr'
  | 'tp_atr'
  | 'train_split'
  | 'slippage'
  | 'commission_pct'
  | 'fixed_spread'

/**
 * Backtest configuration form. Local validation covers obvious input mistakes
 * only; authoritative validation stays server-side. Submits exactly once per
 * explicit "Run Backtest" click and is disabled while a run is in flight.
 */
export function BacktestConfiguration({
  lab,
  initialSymbol,
  running,
  onRun,
  onConfigChange,
}: Props) {
  const bd = lab.backtest_defaults
  const symbols = lab.supported_symbols
  const timeframes = lab.timeframes.map((t) => t.timeframe)

  const [symbol, setSymbol] = useState(() => {
    const req = (initialSymbol ?? '').toUpperCase()
    return req && symbols.includes(req) ? req : symbols[0] ?? 'XAUUSD'
  })
  const [timeframe, setTimeframe] = useState(timeframes[0] ?? '1h')
  const [strategy, setStrategy] = useState(bd.strategy)
  const [mode, setMode] = useState<BacktestMode>('standard')
  const [raw, setRaw] = useState<Record<NumKey, string>>({
    capital: String(bd.capital),
    risk_pct: String(bd.risk_pct),
    sl_atr: String(bd.sl_atr),
    tp_atr: String(bd.tp_atr),
    train_split: '0.8',
    slippage: String(bd.slippage),
    commission_pct: String(bd.commission_pct),
    fixed_spread: String(bd.fixed_spread),
  })

  const set = (k: NumKey, v: string) => setRaw((p) => ({ ...p, [k]: v }))

  const parsed = useMemo(() => {
    const out: Partial<Record<NumKey, number | null>> = {}
    for (const k of Object.keys(raw) as NumKey[]) out[k] = parseNumberInput(raw[k])
    return out as Record<NumKey, number | null>
  }, [raw])

  const errors = useMemo(() => {
    const e: Partial<Record<NumKey | 'symbol', string>> = {}
    if (!symbol) e.symbol = 'Select a symbol'
    if (parsed.capital === null || parsed.capital <= 0) e.capital = 'Positive number required'
    if (parsed.risk_pct === null || parsed.risk_pct <= 0) e.risk_pct = 'Positive number required'
    if (parsed.sl_atr === null || parsed.sl_atr <= 0) e.sl_atr = 'Positive number required'
    if (parsed.tp_atr === null || parsed.tp_atr <= 0) e.tp_atr = 'Positive number required'
    if (mode === 'standard') {
      if (parsed.train_split === null || parsed.train_split < 0.1 || parsed.train_split > 1) {
        e.train_split = 'Between 0.1 and 1.0'
      }
    }
    if (parsed.slippage === null || parsed.slippage < 0) e.slippage = 'Zero or positive'
    if (parsed.commission_pct === null || parsed.commission_pct < 0) e.commission_pct = 'Zero or positive'
    if (parsed.fixed_spread === null || parsed.fixed_spread < 0) e.fixed_spread = 'Zero or positive'
    return e
  }, [symbol, mode, parsed])

  const buildRequest = (): BacktestRunRequest | null => {
    if (Object.keys(errors).length > 0) return null
    return {
      symbol,
      timeframe,
      strategy,
      mode,
      capital: parsed.capital as number,
      risk_pct: parsed.risk_pct as number,
      sl_atr: parsed.sl_atr as number,
      tp_atr: parsed.tp_atr as number,
      train_split: mode === 'standard' ? (parsed.train_split as number) : 1.0,
      slippage: parsed.slippage as number,
      commission_pct: parsed.commission_pct as number,
      fixed_spread: parsed.fixed_spread as number,
      include_monte_carlo: true,
    }
  }

  // Report the current (valid) config upward so the page can detect staleness.
  const current = buildRequest()
  const currentKey = JSON.stringify(current)
  useEffect(() => {
    onConfigChange(current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentKey])

  const submit = (ev: React.FormEvent) => {
    ev.preventDefault()
    const req = buildRequest()
    if (req && !running) onRun(req)
  }

  const num = (k: NumKey, label: string, hint?: string) => (
    <LabeledField label={label} hint={hint} error={errors[k]}>
      {({ id, describedBy }) => (
        <input
          id={id}
          aria-describedby={describedBy}
          aria-invalid={errors[k] ? true : undefined}
          inputMode="decimal"
          value={raw[k]}
          onChange={(e) => set(k, e.target.value)}
          className={inputClass}
        />
      )}
    </LabeledField>
  )

  return (
    <SectionCard title="Backtest configuration">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <LabeledField label="Symbol" error={errors.symbol}>
            {({ id }) => (
              <select
                id={id}
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className={inputClass}
              >
                {symbols.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}
          </LabeledField>

          <LabeledField label="Timeframe">
            {({ id }) => (
              <select
                id={id}
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                className={inputClass}
              >
                {lab.timeframes.map((t) => (
                  <option key={t.timeframe} value={t.timeframe}>
                    {t.timeframe} · {t.period} history
                  </option>
                ))}
              </select>
            )}
          </LabeledField>

          <LabeledField label="Strategy">
            {({ id }) => (
              <select
                id={id}
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className={inputClass}
              >
                {lab.strategies.map((s) => (
                  <option key={s.name} value={s.name}>
                    {s.name} (v{s.version})
                  </option>
                ))}
              </select>
            )}
          </LabeledField>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <span className="text-[11px] uppercase tracking-wider text-muted">Mode</span>
          <SegmentedControl<BacktestMode>
            label="Backtest mode"
            value={mode}
            onChange={setMode}
            options={[
              { value: 'standard', label: 'Standard' },
              { value: 'walk_forward', label: 'Walk-Forward' },
            ]}
          />
          <span className="text-[11px] text-muted">
            {mode === 'walk_forward'
              ? 'Rolling out-of-sample slices with SL/TP grid search (slower).'
              : 'Single chronological in-sample / out-of-sample split.'}
          </span>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {num('capital', 'Initial capital ($)')}
          {num('risk_pct', 'Risk per trade (%)')}
          {num('sl_atr', 'Stop-loss (ATR ×)')}
          {num('tp_atr', 'Take-profit (ATR ×)')}
          {mode === 'standard'
            ? num('train_split', 'Train split', '0.8 → last 20% is out-of-sample')
            : null}
          {num('slippage', 'Slippage')}
          {num('commission_pct', 'Commission (%)')}
          {num('fixed_spread', 'Fixed spread')}
        </div>

        <div className="flex items-center gap-3 border-t border-border-subtle pt-3">
          <button
            type="submit"
            disabled={running || !current}
            className="rounded border border-accent/50 bg-accent/10 px-4 py-1.5 text-sm font-semibold text-accent hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? 'Running backtest…' : 'Run Backtest'}
          </button>
          <span className="text-[11px] text-muted">
            Historical research only — no broker, no live execution. A run takes
            a few seconds to ~15s.
          </span>
        </div>
      </form>
    </SectionCard>
  )
}
