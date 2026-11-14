import type { TextStyle } from 'react-native'

/**
 * "Precision" on the phone. Tokens mirror frontend/src/styles/tokens.css (the dark theme the desktop app uses);
 * the rules behind them are in docs/DESIGN_SYSTEM.md. Screens take colours, type and spacing from here and
 * build from src/components/ui.tsx — never hard-code a colour, a weight above 600 or a one-off card style.
 */
export const colors = {
  background: '#0b0f17',
  surface: '#111722',
  surfaceElevated: '#171e2b',
  surfaceHover: '#1f2836', // pressed rows
  border: 'rgba(160,182,220,0.14)',
  borderSubtle: 'rgba(160,182,220,0.08)',
  textPrimary: '#e8edf5',
  textSecondary: '#a4afc2',
  textMuted: '#77849a',
  positive: '#3ddc97',
  negative: '#f87171',
  warning: '#f5b23d',
  info: '#8b9cff',
  accent: '#5ad1f5', // ice cyan - the one accent (interaction only)
  accentInk: '#04131c', // text on the accent fill
  accentSoft: 'rgba(90,209,245,0.1)', // selected chip / soft fill
  accentSoftStrong: 'rgba(90,209,245,0.16)',
  accentLine: 'rgba(90,209,245,0.42)', // selected chip / feature-card edge
  positiveSoft: 'rgba(61,220,151,0.1)',
  positiveLine: 'rgba(61,220,151,0.35)',
  negativeSoft: 'rgba(248,113,113,0.1)',
  negativeLine: 'rgba(248,113,113,0.42)',
  warningSoft: 'rgba(245,178,61,0.1)',
  warningLine: 'rgba(245,178,61,0.35)',
  infoSoft: 'rgba(139,156,255,0.1)',
  infoLine: 'rgba(139,156,255,0.35)',
} as const

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const

// small radii read as precise (desktop: 5 / 8 / 10); round shapes are only for chips and status dots
export const radius = { sm: 5, md: 8, lg: 10, pill: 999 } as const

/**
 * Geist + Geist Mono, loaded in App.tsx. A custom font on Android has no weights of its own, so each weight
 * is its own family: don't set these by hand. Use `Text` from components/Text, which picks the family from
 * the style's fontWeight (400 / 500 / 600, anything heavier becomes 600) and switches to mono when the
 * style has `fontVariant: ['tabular-nums']` — the mark every price, P&L, time and count already carries.
 */
export const fonts = {
  sans: 'Geist_400Regular',
  sansMedium: 'Geist_500Medium',
  sansSemi: 'Geist_600SemiBold',
  mono: 'GeistMono_400Regular',
  monoMedium: 'GeistMono_500Medium',
  monoSemi: 'GeistMono_600SemiBold',
} as const

/** The type scale (docs/DESIGN_SYSTEM.md §4, sized for a phone). Spread into a style: `{ ...type.body }`. */
export const type = {
  /** screen title */
  title: { fontSize: 24, lineHeight: 30, fontWeight: '600', letterSpacing: -0.4, color: colors.textPrimary },
  /** card title, row title */
  heading: { fontSize: 15, lineHeight: 20, fontWeight: '600', color: colors.textPrimary },
  body: { fontSize: 14, lineHeight: 20, color: colors.textPrimary },
  /** secondary line under a title */
  sub: { fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  /** hints, footnotes */
  small: { fontSize: 12, lineHeight: 17, color: colors.textMuted },
  /** small mono uppercase label (.tl-label) */
  label: { fontSize: 10.5, lineHeight: 14, fontWeight: '500', letterSpacing: 0.9, textTransform: 'uppercase', fontVariant: ['tabular-nums'], color: colors.textMuted },
  /** the one big number on a screen. Sans, not mono: it stands alone, and mono's wide decimal point looks broken at this size */
  hero: { fontSize: 34, lineHeight: 40, fontWeight: '600', letterSpacing: -0.8, color: colors.textPrimary },
  /** a figure in a figure row */
  figure: { fontSize: 18, lineHeight: 24, fontWeight: '600', letterSpacing: -0.3, fontVariant: ['tabular-nums'], color: colors.textPrimary },
  /** inline numbers: prices, row P&L, times */
  num: { fontSize: 14, lineHeight: 20, fontWeight: '500', fontVariant: ['tabular-nums'], color: colors.textPrimary },
} satisfies Record<string, TextStyle>

/** Green / red for money, neutral for zero. P&L always carries its sign too (formatMoney), so colour is never the only signal. */
export function pnlColor(v: number | null | undefined, zero: string = colors.textSecondary): string {
  if (v == null || v === 0 || !Number.isFinite(v)) return zero
  return v > 0 ? colors.positive : colors.negative
}
