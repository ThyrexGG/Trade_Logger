/**
 * Response shape for GET /api/health, mirroring api/schemas.py::HealthResponse.
 * Kept in sync manually — this is a thin typed view, not generated tooling.
 */
export interface HealthResponse {
  status: string
  app_name: string
  version: string
  live_broker_transmission: string
  automation_enabled: boolean
  timestamp: string
}
