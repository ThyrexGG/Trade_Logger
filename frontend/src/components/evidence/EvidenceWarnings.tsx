import type { ReactNode } from 'react'
import type { ForwardEvidenceState } from '../../types/evidence'
import { SectionCard, evidenceTone } from './primitives'
import type { EvidenceTone } from './primitives'

interface Warning {
  id: string
  tone: EvidenceTone
  title: string
  detail: ReactNode
}

const TONE_BORDER: Record<EvidenceTone, string> = {
  positive: 'border-l-positive',
  negative: 'border-l-negative',
  warning: 'border-l-warning',
  info: 'border-l-info',
  neutral: 'border-l-border',
}

/**
 * Statistical warning surface. It only renders concerns the surveillance
 * engine has *already* classified — no threshold logic lives here. If the
 * engine raised nothing, that is stated plainly.
 */
export function EvidenceWarnings({ data }: { data: ForwardEvidenceState }) {
  const u = data.uncertainty
  const a = data.alpha_decay
  const warnings: Warning[] = []

  const uTone = evidenceTone(u.statistical_status)
  if (uTone === 'warning' || uTone === 'negative' || u.statistical_status.includes('INSUFFICIENT')) {
    warnings.push({
      id: 'sample',
      tone: uTone === 'neutral' ? 'warning' : uTone,
      title: u.status_badge,
      detail: u.prohibited_claim || u.valid_statement,
    })
  }

  const aTone = evidenceTone(a.decay_state)
  if (aTone === 'warning' || aTone === 'negative') {
    warnings.push({
      id: 'alpha',
      tone: aTone,
      title: a.decay_state,
      detail: (
        <>
          {a.summary}
          {a.action_required ? (
            <span className="mt-1 block font-mono text-[11px] text-secondary">
              Action: {a.action_required}
            </span>
          ) : null}
        </>
      ),
    })
  }

  if (a.loss_clustering_detected) {
    warnings.push({
      id: 'loss-cluster',
      tone: 'negative',
      title: 'Loss clustering detected',
      detail: 'The engine flagged a cluster of consecutive losing forward observations.',
    })
  }
  if (a.expectancy_deterioration) {
    warnings.push({
      id: 'exp-det',
      tone: 'negative',
      title: 'Expectancy deterioration',
      detail: 'Forward expectancy has turned negative per the surveillance engine.',
    })
  }
  if (a.max_drawdown_expansion === true) {
    warnings.push({
      id: 'dd-expand',
      tone: 'warning',
      title: 'Drawdown expansion',
      detail: 'Forward drawdown exceeds the historical baseline envelope.',
    })
  }

  const cTone = evidenceTone(data.holdout.comparison_verdict)
  if (cTone === 'warning' || cTone === 'negative') {
    warnings.push({
      id: 'holdout',
      tone: cTone,
      title: data.holdout.comparison_verdict,
      detail: data.holdout.explanation,
    })
  }

  const dTone = evidenceTone(data.decision.decision_state)
  if (dTone === 'warning' || dTone === 'negative') {
    warnings.push({
      id: 'decision',
      tone: dTone,
      title: data.decision.decision_state,
      detail: data.decision.research_action,
    })
  }

  return (
    <SectionCard title="Statistical warnings">
      {warnings.length === 0 ? (
        <p className="text-sm text-muted">
          The surveillance engine has not raised any statistical warning for the
          current forward evidence.
        </p>
      ) : (
        <ul className="space-y-2.5">
          {warnings.map((w) => (
            <li
              key={w.id}
              className={`border-l-2 ${TONE_BORDER[w.tone]} bg-surface-elevated/40 px-3 py-2`}
            >
              <p className="text-xs font-semibold text-primary">{w.title}</p>
              <p className="mt-0.5 text-[11px] text-muted">{w.detail}</p>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  )
}
