import Constants, { ExecutionEnvironment } from 'expo-constants'

type NotificationsModule = typeof import('expo-notifications')

/** Expo Go (the developer sandbox app) cannot do remote push on Android; merely importing expo-notifications there crashes the app. */
export const isExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient

let loaded: NotificationsModule | null | undefined

/**
 * expo-notifications, loaded on first use — or null inside Expo Go, so the rest of
 * the app (positions, journal, analytics…) still runs there. In the installed app this always returns the module.
 */
export function getNotifications(): NotificationsModule | null {
  if (loaded !== undefined) return loaded
  if (isExpoGo) {
    loaded = null
    return loaded
  }
  const mod = require('expo-notifications') as NotificationsModule
  // Show the notification even while the app is open (a trade opening is worth a banner).
  mod.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: true,
      shouldSetBadge: false,
    }),
  })
  loaded = mod
  return loaded
}
