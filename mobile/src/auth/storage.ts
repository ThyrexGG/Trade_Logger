import * as SecureStore from 'expo-secure-store'
import type { AuthUser } from '../types/auth'

const TOKEN_KEY = 'tl_session_token'
const USER_KEY = 'tl_session_user'

export interface StoredSession {
  token: string
  user: AuthUser | null
}

/** Reads the saved session from the phone's secure storage (Keychain / Keystore). */
export async function loadSession(): Promise<StoredSession | null> {
  try {
    const token = await SecureStore.getItemAsync(TOKEN_KEY)
    if (!token) return null
    const raw = await SecureStore.getItemAsync(USER_KEY)
    return { token, user: raw ? (JSON.parse(raw) as AuthUser) : null }
  } catch {
    return null
  }
}

export async function saveSession(token: string, user: AuthUser | null): Promise<void> {
  try {
    await SecureStore.setItemAsync(TOKEN_KEY, token)
    if (user) await SecureStore.setItemAsync(USER_KEY, JSON.stringify(user))
  } catch {
    /* secure storage unavailable — the session just won't survive an app restart */
  }
}

export async function clearSession(): Promise<void> {
  try {
    await SecureStore.deleteItemAsync(TOKEN_KEY)
    await SecureStore.deleteItemAsync(USER_KEY)
  } catch {
    /* nothing to clear */
  }
}
