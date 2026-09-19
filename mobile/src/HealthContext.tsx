import { createContext, useContext, type ReactNode } from 'react'
import { useApiHealth } from './useApiHealth'

type Value = ReturnType<typeof useApiHealth>
const Ctx = createContext<Value | null>(null)

/** One shared health poll for the connection banner and the Account screen. */
export function HealthProvider({ children }: { children: ReactNode }) {
  const value = useApiHealth()
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useHealth(): Value {
  const v = useContext(Ctx)
  if (!v) throw new Error('useHealth must be used inside <HealthProvider>')
  return v
}
