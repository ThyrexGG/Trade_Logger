/** Mirrors api/schemas.py::HealthResponse (kept in sync by hand). */
export interface HealthResponse {
  status: string
  app_name: string
  version: string
  live_broker_transmission: string
  automation_enabled: boolean
  timestamp: string
}
