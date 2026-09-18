/** Brand tokens copied from frontend/src/styles/tokens.css (dark theme). */
export const colors = {
  background: '#0a0a0a',
  surface: '#141414',
  surfaceElevated: '#1f1f1f',
  border: 'rgba(255,255,255,0.12)',
  borderSubtle: 'rgba(255,255,255,0.08)',
  textPrimary: '#ffffff',
  textSecondary: '#a3a3a3',
  textMuted: '#737373',
  positive: '#10b981',
  negative: '#ef4444',
  warning: '#f59e0b',
  accent: '#f0b90b', // gold — the brand color
} as const

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 } as const

export const radius = { sm: 6, md: 10, lg: 14, pill: 999 } as const
