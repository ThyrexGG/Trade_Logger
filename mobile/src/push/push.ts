import AsyncStorage from '@react-native-async-storage/async-storage'
import Constants from 'expo-constants'
import * as Device from 'expo-device'
import { Platform } from 'react-native'
import { registerDevice, unregisterDevice } from '../api/push'
import { getNotifications, isExpoGo } from './notifications'

const ENABLED_KEY = 'tl.push.enabled'
const TOKEN_KEY = 'tl.push.token'

export interface PushResult {
  ok: boolean
  /** plain-language reason when ok is false */
  message?: string
}

class PushError extends Error {}

async function acquireToken(): Promise<string> {
  // Expo Go cannot receive remote push on Android (since SDK 53); only the installed app can.
  const Notifications = getNotifications()
  if (isExpoGo || !Notifications) {
    throw new PushError('Trade alerts only work in the installed TradeLogger app, not in Expo Go. See docs/MOBILE_ANDROID_BUILD.md.')
  }
  if (!Device.isDevice) throw new PushError('Push notifications need a real phone, not an emulator.')

  if (Platform.OS === 'android') {
    // The channel must exist before Android 13+ will even show the permission prompt.
    await Notifications.setNotificationChannelAsync('trades', {
      name: 'Trades',
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 200, 100, 200],
      lightColor: '#f0b90b',
    })
  }

  let { status } = await Notifications.getPermissionsAsync()
  if (status !== 'granted') ({ status } = await Notifications.requestPermissionsAsync())
  if (status !== 'granted') {
    throw new PushError('Notifications are blocked. Turn them on for TradeLogger in your phone settings, then try again.')
  }

  const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId
  if (!projectId) {
    throw new PushError('This build has no push project id yet. Finish the EAS setup in docs/MOBILE_ANDROID_BUILD.md and rebuild.')
  }
  try {
    return (await Notifications.getExpoPushTokenAsync({ projectId })).data
  } catch (err) {
    const detail = err instanceof Error ? err.message : String(err)
    throw new PushError(`Could not get a push token (${detail}). On Android this usually means google-services.json is missing from the build.`)
  }
}

async function registerCurrentToken(): Promise<string> {
  const token = await acquireToken()
  await registerDevice(token, Platform.OS, Device.deviceName ?? Device.modelName ?? null)
  await AsyncStorage.setItem(TOKEN_KEY, token)
  return token
}

export async function isPushEnabled(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(ENABLED_KEY)) === '1'
  } catch {
    return false
  }
}

/** Turn trade alerts on: ask permission, get a token, register it with the server. */
export async function enablePush(): Promise<PushResult> {
  try {
    await registerCurrentToken()
    await AsyncStorage.setItem(ENABLED_KEY, '1')
    return { ok: true }
  } catch (err) {
    return { ok: false, message: err instanceof Error ? err.message : 'Could not turn on trade alerts.' }
  }
}

/** Turn alerts off and tell the server to stop pushing to this phone. */
export async function disablePush(): Promise<void> {
  await AsyncStorage.setItem(ENABLED_KEY, '0').catch(() => {})
  await unregisterStoredToken()
}

/** Stop pushing to this phone (used on logout) but keep the on/off preference for the next login. */
export async function unregisterStoredToken(): Promise<void> {
  try {
    const token = await AsyncStorage.getItem(TOKEN_KEY)
    if (token) await unregisterDevice(token)
    await AsyncStorage.removeItem(TOKEN_KEY)
  } catch {
    /* offline or already signed out — the server prunes dead tokens on its own */
  }
}

/** Called on launch / sign-in: tokens can change, so re-register if alerts are on. Silent on failure. */
export async function refreshPushRegistration(): Promise<void> {
  if (!(await isPushEnabled())) return
  try {
    await registerCurrentToken()
  } catch {
    /* surfaced on the Account screen when the user opens it */
  }
}
