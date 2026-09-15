// Handles push notifications while the FlockGuard tab is closed or
// backgrounded. Registered explicitly (see frontend/src/lib/push.js) at its
// own scope alongside the PWA's separate auto-generated service worker
// (vite-plugin-pwa) - the two coexist fine as independent registrations, a
// standard, documented pattern for adding FCM to an existing PWA.
//
// Plain importScripts (not the bundled app's ES modules) because a service
// worker file is served as-is from public/, outside Vite's build.
importScripts('https://www.gstatic.com/firebasejs/12.18.0/firebase-app-compat.js')
importScripts('https://www.gstatic.com/firebasejs/12.18.0/firebase-messaging-compat.js')

// Firebase web config is not a secret (it's the same config already
// embedded in the built frontend bundle) - safe to inline here.
firebase.initializeApp({
  apiKey: 'AIzaSyAf-xdnHHa6702D35gu0jGJLwa8u1t97G8',
  authDomain: 'flockguard-4115e.firebaseapp.com',
  projectId: 'flockguard-4115e',
  storageBucket: 'flockguard-4115e.firebasestorage.app',
  messagingSenderId: '106505547863',
  appId: '1:106505547863:web:8545464d40f2817405b312',
})

const messaging = firebase.messaging()

// The backend (app/services/push_service.py) sends a pure data message, not
// a "notification" message - title/body/url all travel as plain data
// fields. This is deliberate: notification-type messages are handled
// inconsistently across browsers when the tab is in the foreground
// (sometimes routed here anyway instead of to the page's onMessage), so
// data-only keeps background (here) and foreground
// (frontend/src/lib/push.js's onMessage) on one predictable path each.
messaging.onBackgroundMessage((payload) => {
  const { title, body, url } = payload.data || {}
  self.registration.showNotification(title || 'FlockGuard', {
    body: body || '',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: url || '/alerts' },
  })
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const url = event.notification.data?.url || '/alerts'
  event.waitUntil(clients.openWindow(url))
})
