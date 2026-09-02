import type { ReactNode } from 'react'
import { API_BASE_URL } from '../api/client'
import { StatusDot } from '../components/StatusDot'
import { useHealth } from '../lib/useHealth'

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[9rem_1fr] items-start gap-4 py-2">
      <span className="text-sm text-secondary">{label}</span>
      <div className="text-sm text-primary">{children}</div>
    </div>
  )
}

/**
 * Connectivity proof for Stage 4: calls GET /api/health and renders
 * loading / connected / error states. Not a dashboard.
 */
export function HealthCheckPage() {
  const { state, data, error, refetch } = useHealth()
  const apiPath = `${API_BASE_URL || ''}/api/health`

  return (
    <section className="mx-auto max-w-xl">
      <h1 className="text-xl font-semibold">Connectivity Check</h1>
      <p className="mt-1 text-sm text-secondary">
        Verifies the React foundation can reach the FastAPI adapter.
      </p>

      <div className="mt-6 rounded-lg border border-border bg-surface p-6">
        <Row label="Frontend">
          <StatusDot tone="positive" label="Online" />
        </Row>

        <div className="my-2 border-t border-border-subtle" />

        <Row label="FastAPI">
          {state === 'loading' && (
            <StatusDot tone="warning" label="Connecting…" pulse />
          )}
          {state === 'connected' && (
            <StatusDot tone="positive" label="Connected" />
          )}
          {state === 'error' && (
            <StatusDot tone="negative" label="Unreachable" />
          )}
        </Row>

        <Row label="API">
          <code className="font-mono text-xs text-muted">{apiPath}</code>
        </Row>

        <Row label="Status">
          {state === 'loading' && <span className="text-muted">—</span>}
          {state === 'connected' && data && (
            <span className="text-positive">{data.status}</span>
          )}
          {state === 'error' && (
            <span className="text-negative">{error ?? 'Request failed'}</span>
          )}
        </Row>

        {state === 'connected' && data && (
          <>
            <Row label="Backend">
              <span>
                {data.app_name}{' '}
                <span className="text-muted">v{data.version}</span>
              </span>
            </Row>
            <Row label="Safety gate">
              <span className="font-mono text-xs">
                broker={data.live_broker_transmission} · automation=
                {String(data.automation_enabled)}
              </span>
            </Row>
          </>
        )}

        <div className="mt-5">
          <button
            type="button"
            onClick={refetch}
            disabled={state === 'loading'}
            className="rounded border border-border px-3 py-1.5 text-sm text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
          >
            Re-check
          </button>
        </div>
      </div>
    </section>
  )
}
