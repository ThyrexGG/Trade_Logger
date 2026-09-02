import type { ReactNode } from 'react'
import { API_BASE_URL } from '../api/client'
import { useHealth } from '../lib/health'
import { apiStatusView, systemStatusView } from '../lib/status'
import { PageContainer } from '../components/shell/PageContainer'
import { StatusDot } from '../components/shell/StatusDot'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[10rem_1fr] items-start gap-4 border-b border-border-subtle py-2.5 last:border-0">
      <span className="text-sm text-secondary">{label}</span>
      <div className="text-sm text-primary">{children}</div>
    </div>
  )
}

/**
 * `/operations/system` — real backend health from GET /api/health. This is the
 * one shell page backed by live data; everything shown here is returned by the
 * FastAPI adapter.
 */
export function SystemHealthPage() {
  const { state, data, error, lastChecked, refetch } = useHealth()
  const api = apiStatusView(state)
  const system = systemStatusView(state)

  return (
    <PageContainer
      title="System Health"
      description="Backend service status reported by the FastAPI adapter."
      width="standard"
      actions={
        <button
          type="button"
          onClick={refetch}
          disabled={state === 'loading'}
          className="rounded border border-border px-3 py-1.5 text-sm text-primary hover:bg-surface-hover disabled:opacity-50"
        >
          Re-check
        </button>
      }
    >
      <div className="rounded-lg border border-border bg-surface p-5">
        <Row label="API connection">
          <StatusDot tone={api.tone} label={api.label} pulse={api.pulse} />
        </Row>
        <Row label="System status">
          <StatusDot
            tone={system.tone}
            label={system.label}
            pulse={system.pulse}
          />
        </Row>
        <Row label="Endpoint">
          <code className="font-mono text-xs text-muted">
            {`${API_BASE_URL || ''}/api/health`}
          </code>
        </Row>
        <Row label="Last checked">
          {lastChecked ? lastChecked.toLocaleString() : '—'}
        </Row>

        {state === 'connected' && data ? (
          <>
            <Row label="Reported status">
              <span className="text-positive">{data.status}</span>
            </Row>
            <Row label="Service">
              {data.app_name}{' '}
              <span className="text-muted">v{data.version}</span>
            </Row>
            <Row label="Live broker transmission">
              <span className="font-mono text-negative">
                {data.live_broker_transmission}
              </span>
            </Row>
            <Row label="Automation enabled">
              <span className="font-mono">
                {String(data.automation_enabled)}
              </span>
            </Row>
            <Row label="Server time">
              <span className="font-mono text-xs">{data.timestamp}</span>
            </Row>
          </>
        ) : null}

        {state === 'error' ? (
          <Row label="Error">
            <span className="text-negative">{error ?? 'Request failed'}</span>
          </Row>
        ) : null}
      </div>

      <p className="mt-3 text-xs text-muted">
        The shell polls this endpoint on a slow interval and pauses while the tab
        is hidden. Health never blocks navigation.
      </p>
    </PageContainer>
  )
}
