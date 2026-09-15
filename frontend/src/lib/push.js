import { getMessaging, getToken, onMessage, isSupported } from 'firebase/messaging'
import { firebaseApp } from './firebase'
import { api } from './api'

const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY

// Kept as module state (not re-derived per call) so enable/disable within
// the same tab reuse one messaging instance and one SW registration.
let messagingInstance = null

async function getMessagingInstance() {
  if (messagingInstance) return messagingInstance
  if (!(await isSupported())) return null
  messagingInstance = getMessaging(firebaseApp)
  return messagingInstance
}

/** A freshly-registered service worker isn't necessarily "active" yet
 * (it may still be installing) - PushManager.subscribe (which getToken
 * calls under the hood) fails with "no active Service Worker" if you race
 * it, so this waits out that gap before returning. */
async function waitUntilActive(registration) {
  if (registration.active) return registration
  const worker = registration.installing || registration.waiting
  if (!worker) return registration
  await new Promise((resolve) => {
    worker.addEventListener('statechange', function onStateChange() {
      if (worker.state === 'activated') {
        worker.removeEventListener('statechange', onStateChange)
        resolve()
      }
    })
  })
  return registration
}

/** Whether this browser/context can even attempt web push - Safari <16.4,
 * non-HTTPS contexts (other than localhost), and browsers with Notification
 * or Service Worker APIs unavailable all resolve false. */
export async function isPushSupported() {
  return Boolean(VAPID_KEY) && (await isSupported())
}

/** Prompts for notification permission (must be called from a user gesture,
 * e.g. a checkbox click - browsers silently ignore permission requests made
 * outside one), registers the Firebase Messaging service worker, retrieves
 * this device's FCM token, and registers it with the backend so alerts can
 * reach it. Throws with a message safe to show the farmer directly. */
export async function enablePushNotifications() {
  if (!VAPID_KEY) {
    throw new Error('Push notifications are not configured for this deployment yet.')
  }
  const messaging = await getMessagingInstance()
  if (!messaging) {
    throw new Error('Push notifications are not supported in this browser.')
  }

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') {
    throw new Error('Notification permission was not granted.')
  }

  const registration = await waitUntilActive(await navigator.serviceWorker.register('/firebase-messaging-sw.js'))
  const token = await getToken(messaging, { vapidKey: VAPID_KEY, serviceWorkerRegistration: registration })
  if (!token) {
    throw new Error('Could not get a push token for this device.')
  }

  await api.push.register(token)
  return token
}

/** Best-effort - a farmer turning Push off in Settings should stop this
 * device from being sent to, but a failed unregister call (offline, token
 * already gone) must never block saving the rest of their preferences. */
export async function disablePushNotifications() {
  try {
    const messaging = await getMessagingInstance()
    if (!messaging) return
    const registration = await navigator.serviceWorker.getRegistration('/firebase-messaging-sw.js')
    if (!registration) return
    const token = await getToken(messaging, {
      vapidKey: VAPID_KEY,
      serviceWorkerRegistration: await waitUntilActive(registration),
    })
    if (token) await api.push.unregister(token)
  } catch {
    // Best-effort, see above.
  }
}

/** Shows a toast/handler for pushes that arrive while the tab is open and
 * focused - the service worker's onBackgroundMessage only fires when the
 * tab is closed or backgrounded, so foreground delivery needs this. */
export async function onForegroundPush(callback) {
  const messaging = await getMessagingInstance()
  if (!messaging) return () => {}
  return onMessage(messaging, callback)
}
