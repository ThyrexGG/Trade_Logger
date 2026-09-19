import type { KillzoneScanResponse } from '../types/scanner'

const fmtTime = (unixSec: number) =>
  new Date(unixSec * 1000).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })

/** Plain-text/Markdown recap of a scan — for pasting into notes or sharing out of the app. Same layout as
 *  the website's "Copy as Markdown" (frontend/src/pages/KillzoneScannerPage.tsx). */
export function buildScanMarkdown(data: KillzoneScanResponse, ltf: string): string {
  const lines: string[] = []
  lines.push(`# Killzone scan — ${data.symbol}`)
  lines.push('')
  lines.push(`_${new Date(data.timestamp).toLocaleString()} · entry ${ltf} · bias ${data.htf ?? '1h'}_`)
  lines.push('')
  lines.push(`**HTF bias:** ${data.htf_bias ?? 'unknown'}${data.htf_structure?.recent_sequence ? ` — ${data.htf_structure.recent_sequence}` : ''}`)
  if (data.htf_structure?.last_break) lines.push(`- Last break: ${data.htf_structure.last_break}`)
  if (data.htf_structure?.last_swing_high != null) lines.push(`- Last swing high: ${data.htf_structure.last_swing_high}`)
  if (data.htf_structure?.last_swing_low != null) lines.push(`- Last swing low: ${data.htf_structure.last_swing_low}`)
  lines.push('')
  lines.push(`**Current killzone:** ${data.current_killzone ?? 'unknown'}`)
  lines.push('')
  lines.push('**Draw on liquidity:**')
  const bsl = data.htf_liquidity_targets?.bsl ?? []
  const ssl = data.htf_liquidity_targets?.ssl ?? []
  if (bsl.length === 0 && ssl.length === 0) lines.push('- none nearby')
  bsl.forEach((p) => lines.push(`- BSL ${p.price} (${p.distance_from_price} away)`))
  ssl.forEach((p) => lines.push(`- SSL ${p.price} (${p.distance_from_price} away)`))
  lines.push('')
  lines.push(`**Candidate events (${ltf}):**`)
  if (data.candidates.length === 0) {
    lines.push('- none in the recent window')
  } else {
    data.candidates.forEach((c) => {
      const plan = `entry ${c.potential_entry} / stop ${c.potential_stop}${
        c.potential_target != null ? ` / target ${c.potential_target} (R:R ${c.risk_reward})` : ' / no target nearby'
      }`
      lines.push(
        `- ${c.direction.toUpperCase()} — sweep ${c.sweep_level} (${fmtTime(c.sweep_time)}) → shift ${c.shift_level} (${fmtTime(c.shift_time)}), ${c.killzone}, ${c.agrees_with_htf_bias ? 'agrees with' : 'conflicts with'} HTF bias — ${plan} — confluence ${c.confluence_score}/5`,
      )
    })
  }
  lines.push('')
  lines.push('**Unmitigated FVGs:**')
  if (data.recent_unmitigated_fvgs.length === 0) {
    lines.push('- none currently')
  } else {
    data.recent_unmitigated_fvgs.forEach((f) =>
      lines.push(`- ${f.type} ${f.bottom}–${f.top} — confirmed ${fmtTime(f.creation_time)} (${f.age_candles} candles ago)`),
    )
  }
  lines.push('')
  lines.push(`_Pattern-flagging only, not a signal — data source: ${data.ltf_source ?? 'unknown'} / ${data.htf_source ?? 'unknown'}._`)
  return lines.join('\n')
}
