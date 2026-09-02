import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { RiskPreviewRequest } from '../types/risk'
import { useHealth } from '../lib/health'
import { useRiskPreview } from '../lib/useRiskPreview'
import { useWatchlist } from '../lib/useWatchlist'
import { useOpenPositions } from '../lib/useOpenPositions'
import { PageContainer } from '../components/shell/PageContainer'
import { RiskCalculator } from '../components/risk/RiskCalculator'
import { RiskResult } from '../components/risk/RiskResult'
import { OpenExposure } from '../components/risk/OpenExposure'

/** Stable key for a request, to detect when displayed result no longer matches inputs. */
function requestKey(req: RiskPreviewRequest | null): string {
  if (!req) return ''
  return JSON.stringify([
    req.symbol,
    req.side,
    req.entry_price,
    req.stop_loss,
    req.take_profit_1 ?? null,
    req.take_profit_2 ?? null,
    req.requested_risk_pct,
    req.account_balance,
  ])
}

export function RiskGatewayPage() {
  const [searchParams] = useSearchParams()
  const health = useHealth()
  const watchlist = useWatchlist()
  const positions = useOpenPositions()
  const risk = useRiskPreview()

  const [pendingRequest, setPendingRequest] = useState<RiskPreviewRequest | null>(
    null,
  )
  const onRequestChange = useCallback(
    (req: RiskPreviewRequest | null) => setPendingRequest(req),
    [],
  )

  const symbols = useMemo(
    () => watchlist.items.map((i) => i.symbol),
    [watchlist.items],
  )
  const initialSymbol =
    searchParams.get('symbol')?.toUpperCase() || symbols[0] || 'XAUUSD'

  const isStale =
    risk.result !== null &&
    pendingRequest !== null &&
    requestKey(pendingRequest) !== requestKey(risk.resultRequest)

  const retry = useCallback(() => {
    if (pendingRequest) risk.calculate(pendingRequest)
  }, [pendingRequest, risk])

  const automationDisabled =
    health.data?.automation_enabled === false || health.state !== 'connected'
  const brokerState = health.data?.live_broker_transmission ?? 'BLOCKED'

  return (
    <PageContainer
      title="Risk Gateway"
      description="Authoritative pre-trade position sizing. Planning only — nothing is executed."
    >
      <div className="mx-auto w-full max-w-5xl space-y-4">
        <div
          role="note"
          className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded border border-negative/30 bg-negative/10 px-3 py-2 font-mono text-[11px] text-negative"
        >
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true">🔒</span>
            LIVE AUTOMATION: {automationDisabled ? 'DISABLED' : 'CHECK'}
          </span>
          <span>LIVE BROKER TRANSMISSION: {brokerState}</span>
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-lg border border-border bg-surface p-4">
            <RiskCalculator
              symbols={symbols}
              initialSymbol={initialSymbol}
              calculating={risk.state === 'calculating'}
              onSubmit={risk.calculate}
              onRequestChange={onRequestChange}
            />
          </div>

          <div className="space-y-4">
            <div className="rounded-lg border border-border bg-surface p-4">
              <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-secondary">
                Authoritative result
              </p>
              <RiskResult
                state={risk.state}
                result={risk.result}
                error={risk.error}
                isStale={isStale}
                onRetry={retry}
              />
            </div>

            <div className="rounded-lg border border-border bg-surface p-4">
              <OpenExposure
                state={positions.state}
                data={positions.data}
                error={positions.error}
              />
            </div>
          </div>
        </div>
      </div>
    </PageContainer>
  )
}
