import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { HealthCheckPage } from './pages/HealthCheckPage'

/**
 * Routing foundation. Only the connectivity screen exists in Stage 4;
 * terminal routes are added in later stages.
 */
export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<HealthCheckPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  )
}
