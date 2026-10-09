/** Brand tokens copied from frontend/src/styles/tokens.css (the "Precision" dark theme the desktop app uses). */
export const colors = {
  background: '#0b0f17',
  surface: '#111722',
  surfaceElevated: '#171e2b',
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
  accentLine: 'rgba(90,209,245,0.42)', // selected chip / outlined button edge
  negativeSoft: 'rgba(248,113,113,0.1)',
  negativeLine: 'rgba(248,113,113,0.42)',
  warningSoft: 'rgba(245,178,61,0.1)',
  warningLine: 'rgba(245,178,61,0.35)',
} as const

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const

// small radii read as precise (desktop: 5 / 8 / 10); round shapes are only for chips and status dots
export const radius = { sm: 5, md: 8, lg: 10, pill: 999 } as const
