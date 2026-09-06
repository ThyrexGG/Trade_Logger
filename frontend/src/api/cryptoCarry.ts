import { apiGet } from './client'
import type {
  CarryForwardResponse,
  FundingCarryResponse,
  PortfolioConstructionResponse,
} from '../types/cryptoCarry'

/** GET /api/research/funding-carry-forward — Phase 98 weekly forward evidence. */
export function getCarryForward(signal?: AbortSignal): Promise<CarryForwardResponse> {
  return apiGet<CarryForwardResponse>('/api/research/funding-carry-forward', { signal })
}

/** GET /api/research/portfolio-construction — Phase 97 sizing + recommended book. */
export function getPortfolioConstruction(
  signal?: AbortSignal,
): Promise<PortfolioConstructionResponse> {
  return apiGet<PortfolioConstructionResponse>('/api/research/portfolio-construction', { signal })
}

/** GET /api/research/funding-carry — Phase 96 edge test. */
export function getFundingCarry(signal?: AbortSignal): Promise<FundingCarryResponse> {
  return apiGet<FundingCarryResponse>('/api/research/funding-carry', { signal })
}
