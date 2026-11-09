import { initializeApp } from 'firebase/app'
import {
  getAuth,
  onAuthStateChanged,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth'
import { useAuthStore } from '../store/useAuthStore'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const firebaseApp = initializeApp(firebaseConfig)
export const auth = getAuth(firebaseApp)

export function watchAuthState() {
  return onAuthStateChanged(auth, (user) => {
    useAuthStore.getState().setUser(user)
  })
}

// Firebase caches the ID token and silently refreshes it before expiry -
// always ask for it fresh at call time rather than storing one ourselves.
export function getIdToken() {
  return auth.currentUser ? auth.currentUser.getIdToken() : Promise.resolve(null)
}

// A newly set custom claim (e.g. `org_id`, after accepting a team
// invitation - see app/api/routes/team.py::accept_invitation) only shows
// up on a freshly minted token. `getIdToken(true)` forces Firebase to
// fetch one rather than reusing its cached token.
export function forceRefreshToken() {
  return auth.currentUser ? auth.currentUser.getIdToken(true) : Promise.resolve(null)
}

// The platform_admin claim (granted by backend/scripts/grant_platform_admin.py)
// only decides whether to SHOW the admin console - the backend re-checks it
// on every /admin request, so editing this in devtools gets you nothing.
// `forceRefresh` fetches a new token so a just-granted claim shows up
// without signing out (a cached token can be up to an hour old).
export async function hasPlatformAdminClaim(forceRefresh = false) {
  if (!auth.currentUser) return false
  const result = await auth.currentUser.getIdTokenResult(forceRefresh)
  return result.claims.platform_admin === true
}

export function registerWithEmail(email, password) {
  return createUserWithEmailAndPassword(auth, email, password)
}

export function loginWithEmail(email, password) {
  return signInWithEmailAndPassword(auth, email, password)
}

export function logout() {
  return signOut(auth)
}
