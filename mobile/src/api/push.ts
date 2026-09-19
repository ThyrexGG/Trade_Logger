import { apiPost } from './client'

export interface TestPushResult {
  sent: number
  tickets: number
  devices: number
  error: string | null
  push_enabled: boolean
}

/** POST /api/push/register — save this phone's Expo push token for the signed-in user. */
export function registerDevice(token: string, platform: string, deviceName: string | null) {
  return apiPost<{ ok: boolean; devices: number }>('/api/push/register', {
    token,
    platform,
    ...(deviceName ? { device_name: deviceName } : {}),
  })
}

/** POST /api/push/unregister — stop pushing to this phone. */
export function unregisterDevice(token: string) {
  return apiPost<{ ok: boolean; removed: boolean }>('/api/push/unregister', { token })
}

/** POST /api/push/test — sends a real test notification and reports what Expo answered. */
export function sendTestPush() {
  return apiPost<TestPushResult>('/api/push/test', {})
}
