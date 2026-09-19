import { createContext, useContext, type ReactNode } from 'react'
import { usePositions, type UsePositions } from '../usePositions'

const Ctx = createContext<UsePositions | null>(null)

/** One shared positions poller for every tab (Positions + Journal's "Open now"). */
export function PositionsProvider({ children }: { children: ReactNode }) {
  const value = usePositions()
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function usePositionsContext(): UsePositions {
  const v = useContext(Ctx)
  if (!v) throw new Error('usePositionsContext must be used inside <PositionsProvider>')
  return v
}
