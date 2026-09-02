import { Link } from 'react-router-dom'
import type { CommandCenterOverviewResponse } from '../../types/commandCenter'
import { SectionCard } from '../intelligence/primitives'
import { OpsMetric, OpsStatusTag, OpsUnavailable } from '../operations/primitives'
import { formatPercent, formatUsd, timeAgo } from '../../lib/format'

function signedUsd(v: number): string {
  return `${v >= 0 ? '+' : ''}${formatUsd(v)}`
}
function tone(v: number): 'positive' | 'negative' | 'neutral' {
  return v > 0 ? 'positive' : v < 0 ? 'negative' : 'neutral'
}

/** A section that failed to build server-side. */
function Degraded({ name }: { name: string }) {
  return (
    <OpsUnavailable>
      <code>{name}</code> is temporarily unavailable — its source could not be
      read. Other sections are unaffected.
    </OpsUnavailable>
  )
}

export function CommandCenterView({ data }: { data: CommandCenterOverviewResponse }) {
  const d = data
  const degraded = new Set(d.sections_degraded)
  const daily = d.daily_performance
  const acct = d.account_summary
  const pos = d.positions
  const alerts = d.alerts
  const mkt = d.market_context
  const research = d.research_state

  return (
    <div className="space-y-4">
      {/* Session + safety hero */}
      <SectionCard
        title="Right now"
        action={<span className="font-mono text-[11px] text-muted">{d.session.utc_time}</span>}
      >
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <div>
            <span className="text-muted">Session </span>
            <span className="font-mono font-semibold text-primary">{d.session.current_session}</span>
          </div>
          <div>
            <span className="text-muted">Next </span>
            <span className="font-mono text-secondary">
              {d.session.next_session}
              {d.session.next_session_in_min != null ? ` · ${d.session.next_session_in_min}m` : ''}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <OpsStatusTag value={d.safety.overall_status} size="sm" />
            <span className="text-muted">automation</span>
            <span className={d.safety.automation_enabled ? 'text-negative' : 'text-positive'}>
              {d.safety.automation_enabled ? 'ENABLED' : 'DISABLED'}
            </span>
            <span className="text-muted">· broker</span>
            <span className="text-positive">{d.safety.live_broker_transmission}</span>
            {d.safety.kill_switch_engaged ? <span className="text-warning">· KILL SWITCH</span> : null}
          </div>
        </div>
      </SectionCard>

      {/* Today */}
      <SectionCard title={`Today — ${daily?.date ?? '—'}`}>
        {degraded.has('daily_performance') || !daily ? (
          <Degraded name="daily_performance" />
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <OpsMetric label="Net P&L today" value={signedUsd(daily.net_pnl)} tone={tone(daily.net_pnl)} />
            <OpsMetric label="Trades today" value={daily.trades} sub={`${daily.wins}W / ${daily.losses}L`} />
            <OpsMetric
              label="Win rate today"
              value={daily.trades > 0 ? formatPercent(daily.win_rate) : '—'}
            />
            <OpsMetric
              label="Gross W / L"
              value={`${formatUsd(daily.gross_profit)} / ${formatUsd(daily.gross_loss)}`}
            />
          </div>
        )}
      </SectionCard>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Account */}
        <SectionCard
          title="Account"
          action={<Link to="/workspace/analytics" className="font-mono text-[11px] text-accent hover:underline">analytics →</Link>}
        >
          {degraded.has('account_summary') || !acct ? (
            <Degraded name="account_summary" />
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <OpsMetric
                label={acct.official_balance != null ? 'Balance (broker)' : 'Balance (derived)'}
                value={formatUsd(acct.official_balance ?? acct.derived_balance)}
              />
              <OpsMetric label="All-time net P&L" value={signedUsd(acct.all_time_net_pnl)} tone={tone(acct.all_time_net_pnl)} />
              <OpsMetric label="Profit factor" value={acct.profit_factor.toFixed(2)} sub={`${acct.all_time_trades} trades · ${formatPercent(acct.all_time_win_rate)} win`} />
              <OpsMetric
                label="Max drawdown"
                value={formatPercent(acct.max_drawdown_pct)}
                tone={acct.max_drawdown_pct >= 10 ? 'negative' : acct.max_drawdown_pct >= 5 ? 'warning' : 'neutral'}
              />
            </div>
          )}
        </SectionCard>

        {/* Positions */}
        <SectionCard
          title="Open positions"
          action={<Link to="/workspace/positions" className="font-mono text-[11px] text-accent hover:underline">positions →</Link>}
        >
          {degraded.has('positions') || !pos ? (
            <Degraded name="positions" />
          ) : pos.total_open === 0 ? (
            <OpsUnavailable>No open positions.</OpsUnavailable>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-2">
                <OpsMetric label="Open" value={pos.total_open} sub={`${pos.long_count}L / ${pos.short_count}S`} />
                <OpsMetric label="Floating P&L" value={signedUsd(pos.total_floating_pnl)} tone={tone(pos.total_floating_pnl)} />
                <OpsMetric label="Symbols" value={pos.by_symbol.length} />
              </div>
              <table className="mt-2 w-full border-collapse text-[11px]">
                <tbody>
                  {pos.by_symbol.map((s) => (
                    <tr key={s.symbol} className="border-b border-border-subtle/60">
                      <td className="py-1 font-mono font-semibold text-primary">{s.symbol}</td>
                      <td className="py-1 text-right font-mono text-secondary">{s.count}×</td>
                      <td className={`py-1 text-right font-mono tabular-nums ${s.floating_pnl > 0 ? 'text-positive' : s.floating_pnl < 0 ? 'text-negative' : 'text-secondary'}`}>
                        {signedUsd(s.floating_pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </SectionCard>

        {/* Alerts */}
        <SectionCard
          title="Alerts"
          action={<Link to="/workspace/alerts" className="font-mono text-[11px] text-accent hover:underline">alerts →</Link>}
        >
          {degraded.has('alerts') || !alerts ? (
            <Degraded name="alerts" />
          ) : (
            <>
              <div className="grid grid-cols-2 gap-2">
                <OpsMetric label="Active" value={alerts.active} tone={alerts.active > 0 ? 'info' : 'neutral'} />
                <OpsMetric label="Triggered" value={alerts.triggered} tone={alerts.triggered > 0 ? 'warning' : 'neutral'} />
              </div>
              {alerts.triggered_recent.length > 0 ? (
                <ul className="mt-2 space-y-1 text-[11px]">
                  {alerts.triggered_recent.map((a) => (
                    <li key={a.id} className="font-mono text-warning">
                      {a.symbol} {a.condition === 'ABOVE' ? '≥' : '≤'} {formatUsd(a.target_price)}
                      {a.triggered_at ? <span className="text-muted"> · {a.triggered_at.slice(0, 16).replace('T', ' ')}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : alerts.active === 0 ? (
                <p className="mt-2 text-[11px] text-muted">No price alerts set.</p>
              ) : null}
            </>
          )}
        </SectionCard>

        {/* Market context */}
        <SectionCard
          title="Market context"
          action={<Link to="/research/intelligence" className="font-mono text-[11px] text-accent hover:underline">intelligence →</Link>}
        >
          {degraded.has('market_context') || !mkt ? (
            <Degraded name="market_context" />
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <OpsMetric label="Primary regime" value={mkt.primary_regime} sub={`${mkt.regime_confidence_pct.toFixed(0)}% confidence`} />
              <OpsMetric label="USD strength" value={mkt.usd_strength_state} />
              <OpsMetric label="Breadth" value={`${mkt.breadth_bullish_pct.toFixed(0)}% bull`} sub={`${mkt.breadth_bearish_pct.toFixed(0)}% bear`} />
              <OpsMetric label="Strong / weak" value={`${mkt.strongest_asset} / ${mkt.weakest_asset}`} sub={`data quality ${mkt.data_quality}`} />
            </div>
          )}
        </SectionCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Watchlist highlights */}
        <SectionCard
          title="Watchlist highlights"
          action={<Link to="/workspace/market" className="font-mono text-[11px] text-accent hover:underline">market →</Link>}
        >
          {degraded.has('watchlist_highlights') || d.watchlist_highlights.length === 0 ? (
            degraded.has('watchlist_highlights')
              ? <Degraded name="watchlist_highlights" />
              : <OpsUnavailable>No watchlist data.</OpsUnavailable>
          ) : (
            <table className="w-full border-collapse text-[11px]">
              <tbody>
                {d.watchlist_highlights.map((w) => (
                  <tr key={w.symbol} className="border-b border-border-subtle/60">
                    <td className="py-1 font-mono font-semibold text-primary">{w.symbol}</td>
                    <td className="py-1 text-right font-mono tabular-nums text-secondary">{w.last_price != null ? w.last_price : '—'}</td>
                    <td className="py-1 text-right font-mono text-muted">{w.bias ?? '—'}</td>
                    <td className="py-1 text-right font-mono tabular-nums text-secondary">{w.score != null ? w.score.toFixed(0) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </SectionCard>

        {/* Research */}
        <SectionCard
          title="Research state"
          action={<Link to="/evidence/forward" className="font-mono text-[11px] text-accent hover:underline">evidence →</Link>}
        >
          {degraded.has('research_state') || !research ? (
            <Degraded name="research_state" />
          ) : (
            <div>
              <div className="flex items-center gap-2">
                <OpsStatusTag value={research.decision_state} size="sm" />
                <span className="font-mono text-[11px] text-muted">N = {research.sample_n}</span>
              </div>
              <p className="mt-2 text-[11px] text-secondary">{research.headline}</p>
            </div>
          )}
          {d.research_notes.length > 0 ? (
            <ul className="mt-3 space-y-1.5 border-t border-border-subtle pt-2 text-[11px]">
              {d.research_notes.map((n) => (
                <li key={n.note_id}>
                  <span className="font-mono text-muted">{timeAgo(n.created_at) ?? n.created_at.slice(0, 10)} · {n.category}</span>
                  <br />
                  <span className="text-secondary">{n.note_text}</span>
                </li>
              ))}
            </ul>
          ) : degraded.has('research_notes') ? (
            <p className="mt-2 text-[11px] text-muted">Research notes unavailable.</p>
          ) : null}
        </SectionCard>
      </div>

      {d.sections_degraded.length > 0 ? (
        <p className="rounded border border-warning/30 bg-warning/10 px-2 py-1 text-[11px] text-warning">
          {d.sections_degraded.length} section(s) degraded: {d.sections_degraded.join(', ')}. The
          overview still reflects every source that responded.
        </p>
      ) : null}
    </div>
  )
}
