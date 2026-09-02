import { useEffect, useMemo, useState } from 'react'
import type { RiskPreviewRequest } from '../../types/risk'
import { parseNumberInput } from '../../lib/format'
import { LabeledField, SegmentedControl, inputClass } from './fields'

interface RiskCalculatorProps {
  symbols: string[]
  initialSymbol: string
  calculating: boolean
  onSubmit: (req: RiskPreviewRequest) => void
  /** Emits the current locally-valid request (or null) so the page can flag staleness. */
  onRequestChange: (req: RiskPreviewRequest | null) => void
}

interface FormState {
  symbol: string
  side: 'BUY' | 'SELL'
  accountBalance: string
  riskPct: string
  entryPrice: string
  stopLoss: string
  takeProfit1: string
  takeProfit2: string
}

const DEFAULTS: Omit<FormState, 'symbol'> = {
  side: 'BUY',
  accountBalance: '10000',
  riskPct: '1.0',
  entryPrice: '',
  stopLoss: '',
  takeProfit1: '',
  takeProfit2: '',
}

type Errors = Partial<Record<keyof FormState, string>>

function validate(form: FormState): { req: RiskPreviewRequest | null; errors: Errors } {
  const errors: Errors = {}

  const balance = parseNumberInput(form.accountBalance)
  if (balance === null) errors.accountBalance = 'Enter a number'
  else if (balance <= 0) errors.accountBalance = 'Must be greater than 0'

  const riskPct = parseNumberInput(form.riskPct)
  if (riskPct === null) errors.riskPct = 'Enter a number'
  else if (riskPct <= 0) errors.riskPct = 'Must be greater than 0'

  const entry = parseNumberInput(form.entryPrice)
  if (entry === null) errors.entryPrice = 'Required'
  else if (entry <= 0) errors.entryPrice = 'Must be greater than 0'

  const stop = parseNumberInput(form.stopLoss)
  if (stop === null) errors.stopLoss = 'Required'
  else if (stop <= 0) errors.stopLoss = 'Must be greater than 0'

  if (entry !== null && stop !== null && entry === stop) {
    errors.stopLoss = 'Stop loss cannot equal entry'
  }

  let tp1: number | null = null
  if (form.takeProfit1.trim() !== '') {
    tp1 = parseNumberInput(form.takeProfit1)
    if (tp1 === null || tp1 <= 0) errors.takeProfit1 = 'Must be a positive number'
  }
  let tp2: number | null = null
  if (form.takeProfit2.trim() !== '') {
    tp2 = parseNumberInput(form.takeProfit2)
    if (tp2 === null || tp2 <= 0) errors.takeProfit2 = 'Must be a positive number'
  }

  if (
    Object.keys(errors).length > 0 ||
    balance === null ||
    riskPct === null ||
    entry === null ||
    stop === null
  ) {
    return { req: null, errors }
  }

  return {
    req: {
      symbol: form.symbol,
      side: form.side,
      entry_price: entry,
      stop_loss: stop,
      take_profit_1: tp1,
      take_profit_2: tp2,
      requested_risk_pct: riskPct,
      account_balance: balance,
    },
    errors,
  }
}

/**
 * Risk-planning form. Local validation only (required / numeric / positive /
 * entry≠stop) — all sizing math is the backend's. POST happens on the explicit
 * Calculate button, never on change.
 */
export function RiskCalculator({
  symbols,
  initialSymbol,
  calculating,
  onSubmit,
  onRequestChange,
}: RiskCalculatorProps) {
  const [form, setForm] = useState<FormState>({ symbol: initialSymbol, ...DEFAULTS })
  const [showErrors, setShowErrors] = useState(false)

  // keep symbol in sync if the page's initial symbol changes (workspace handoff)
  useEffect(() => {
    setForm((f) => (f.symbol === initialSymbol ? f : { ...f, symbol: initialSymbol }))
  }, [initialSymbol])

  const { req, errors } = useMemo(() => validate(form), [form])

  useEffect(() => {
    onRequestChange(req)
  }, [req, onRequestChange])

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }))
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!req) {
      setShowErrors(true)
      return
    }
    setShowErrors(false)
    onSubmit(req)
  }

  const err = (k: keyof FormState) => (showErrors ? errors[k] : undefined)

  const symbolOptions = symbols.includes(form.symbol)
    ? symbols
    : [form.symbol, ...symbols]

  return (
    <form onSubmit={submit} className="flex flex-col gap-5" noValidate>
      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-xs font-semibold uppercase tracking-wider text-secondary">
          Risk inputs
        </legend>

        <div className="grid gap-3 sm:grid-cols-2">
          <LabeledField label="Symbol">
            {({ id }) => (
              <select
                id={id}
                value={form.symbol}
                onChange={(e) => set('symbol', e.target.value)}
                className={inputClass}
              >
                {symbolOptions.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}
          </LabeledField>

          <div className="flex flex-col gap-1">
            <span className="text-[11px] uppercase tracking-wider text-muted">
              Side
            </span>
            <SegmentedControl
              label="Trade side"
              value={form.side}
              onChange={(v) => set('side', v)}
              options={[
                { value: 'BUY', label: 'BUY' },
                { value: 'SELL', label: 'SELL' },
              ]}
            />
          </div>

          <LabeledField label="Account balance" error={err('accountBalance')}>
            {({ id, describedBy }) => (
              <input
                id={id}
                inputMode="decimal"
                value={form.accountBalance}
                onChange={(e) => set('accountBalance', e.target.value)}
                aria-invalid={!!err('accountBalance')}
                aria-describedby={describedBy}
                className={inputClass}
              />
            )}
          </LabeledField>

          <LabeledField
            label="Risk %"
            hint="Percentage of balance"
            error={err('riskPct')}
          >
            {({ id, describedBy }) => (
              <input
                id={id}
                inputMode="decimal"
                value={form.riskPct}
                onChange={(e) => set('riskPct', e.target.value)}
                aria-invalid={!!err('riskPct')}
                aria-describedby={describedBy}
                className={inputClass}
              />
            )}
          </LabeledField>
        </div>
      </fieldset>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-1 text-xs font-semibold uppercase tracking-wider text-secondary">
          Trade parameters
        </legend>

        <div className="grid gap-3 sm:grid-cols-2">
          <LabeledField label="Entry price" error={err('entryPrice')}>
            {({ id, describedBy }) => (
              <input
                id={id}
                inputMode="decimal"
                value={form.entryPrice}
                onChange={(e) => set('entryPrice', e.target.value)}
                placeholder="e.g. 159.800"
                aria-invalid={!!err('entryPrice')}
                aria-describedby={describedBy}
                className={inputClass}
              />
            )}
          </LabeledField>

          <LabeledField
            label="Stop loss"
            hint="Price — not pips"
            error={err('stopLoss')}
          >
            {({ id, describedBy }) => (
              <input
                id={id}
                inputMode="decimal"
                value={form.stopLoss}
                onChange={(e) => set('stopLoss', e.target.value)}
                placeholder="e.g. 160.100"
                aria-invalid={!!err('stopLoss')}
                aria-describedby={describedBy}
                className={inputClass}
              />
            )}
          </LabeledField>

          <LabeledField label="Take profit 1" optional error={err('takeProfit1')}>
            {({ id, describedBy }) => (
              <input
                id={id}
                inputMode="decimal"
                value={form.takeProfit1}
                onChange={(e) => set('takeProfit1', e.target.value)}
                aria-invalid={!!err('takeProfit1')}
                aria-describedby={describedBy}
                className={inputClass}
              />
            )}
          </LabeledField>

          <LabeledField label="Take profit 2" optional error={err('takeProfit2')}>
            {({ id, describedBy }) => (
              <input
                id={id}
                inputMode="decimal"
                value={form.takeProfit2}
                onChange={(e) => set('takeProfit2', e.target.value)}
                aria-invalid={!!err('takeProfit2')}
                aria-describedby={describedBy}
                className={inputClass}
              />
            )}
          </LabeledField>
        </div>
      </fieldset>

      {showErrors && !req ? (
        <p role="alert" className="text-xs text-negative">
          Fix the highlighted fields before calculating.
        </p>
      ) : null}

      <button
        type="submit"
        disabled={calculating}
        className="self-start rounded border border-accent/50 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent hover:bg-accent/20 disabled:opacity-50"
      >
        {calculating ? 'Calculating…' : 'Calculate Risk'}
      </button>
    </form>
  )
}
