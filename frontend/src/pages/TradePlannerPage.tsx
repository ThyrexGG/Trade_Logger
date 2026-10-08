import { useSearchParams } from 'react-router-dom'
import { PageContainer } from '../components/shell/PageContainer'
import { DisclaimerNote } from '../components/shared/DisclaimerNote'
import { KillzoneScannerView, type KillzoneTab } from '../components/planner/KillzoneScannerView'
import { ChartAnalyzerView } from '../components/planner/ChartAnalyzerView'

type PlannerTab = 'find' | 'board' | 'chart' | 'plan'

const TABS: { id: PlannerTab; label: string; hint: string }[] = [
  { id: 'find', label: 'Find setups', hint: 'Scan one market for the setup' },
  { id: 'board', label: 'All my markets', hint: 'Scan every market you watch at once' },
  { id: 'chart', label: 'Check my chart', hint: 'Upload a chart for a second opinion' },
  { id: 'plan', label: 'Write my plan', hint: 'Entry, stop, target and why — before you trade' },
]

const TO_KILLZONE: Record<Exclude<PlannerTab, 'chart'>, KillzoneTab> = { find: 'scan', board: 'board', plan: 'plan' }
const FROM_KILLZONE: Record<KillzoneTab, PlannerTab> = { scan: 'find', board: 'board', plan: 'plan' }

function parseTab(raw: string | null): PlannerTab {
  return TABS.some((t) => t.id === raw) ? (raw as PlannerTab) : 'find'
}

/**
 * Trade Planner (`/workspace/trade-planner`) — everything before a trade in
 * one place: find a setup (the killzone scanner's Scan + Board), get a second
 * opinion on your own chart (the chart analyzer), and write the plan. The tab
 * lives in the URL (`?tab=chart`) so links can open a specific step. Both
 * views stay mounted while you switch, so a scan result or an uploaded chart
 * isn't lost when you hop between tabs.
 */
export function TradePlannerPage() {
  const [params, setParams] = useSearchParams()
  const tab = parseTab(params.get('tab'))
  // The killzone view remembers which of its own tabs was last open while "Check my chart" is showing.
  const killzoneTab: KillzoneTab = tab === 'chart' ? TO_KILLZONE[parseKzMemory(params)] : TO_KILLZONE[tab]

  function go(next: PlannerTab) {
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev)
        if (next === 'find') p.delete('tab')
        else p.set('tab', next)
        if (next !== 'chart') p.delete('kz')
        else if (tab !== 'chart') p.set('kz', tab)
        return p
      },
      { replace: true },
    )
  }

  return (
    <PageContainer title="Trade Planner">
      <div className="space-y-4">
        <DisclaimerNote />

        <div className="tl-seg grid grid-cols-2 sm:inline-flex" role="tablist" aria-label="Trade Planner steps">
          {TABS.map((t) => (
            <button
              key={t.id}
              type="button"
              role="tab"
              aria-selected={tab === t.id}
              title={t.hint}
              onClick={() => go(t.id)}
              className="!h-8 !px-3.5"
            >
              {t.label}
            </button>
          ))}
        </div>

        <div hidden={tab === 'chart'}>
          <KillzoneScannerView tab={killzoneTab} onTabChange={(t) => go(FROM_KILLZONE[t])} />
        </div>
        <div hidden={tab !== 'chart'}>
          <ChartAnalyzerView />
        </div>
      </div>
    </PageContainer>
  )
}

function parseKzMemory(params: URLSearchParams): Exclude<PlannerTab, 'chart'> {
  const kz = params.get('kz')
  return kz === 'board' || kz === 'plan' ? kz : 'find'
}
