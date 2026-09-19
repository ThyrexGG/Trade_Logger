import * as Notifications from 'expo-notifications'
import { useEffect, useRef } from 'react'
import { useJournal } from '../journal/JournalContext'
import { openFromNotification } from '../navigation/ref'
import { usePositionsContext } from '../positions/PositionsContext'
import { refreshPushRegistration } from './push'

/**
 * Renders nothing. While signed in it (1) keeps this phone's push token
 * registered, (2) refreshes positions + journal when a notification arrives so
 * the screen already shows the new trade, and (3) opens the trade when a
 * notification is tapped — including a tap that launched the app.
 */
export function PushBridge() {
  const positions = usePositionsContext()
  const journal = useJournal()
  const refreshAll = useRef(() => {})
  refreshAll.current = () => {
    positions.refresh()
    void journal.refresh()
  }

  useEffect(() => {
    void refreshPushRegistration()

    const received = Notifications.addNotificationReceivedListener(() => refreshAll.current())
    const tapped = Notifications.addNotificationResponseReceivedListener((response) => {
      refreshAll.current()
      openFromNotification(response.notification.request.content.data)
    })

    // App was launched by tapping a notification.
    void Notifications.getLastNotificationResponseAsync().then((response) => {
      if (response) {
        refreshAll.current()
        openFromNotification(response.notification.request.content.data)
      }
    })

    return () => {
      received.remove()
      tapped.remove()
    }
  }, [])

  return null
}
