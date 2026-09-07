import { initializeApp } from 'firebase/app'
import {
  getAuth,
  onAuthStateChanged,
  createUserWithEmailAndPassword,
  signInWithEmailAndPassword,
  signOut,
  sendPasswordResetEmail,
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

export function registerWithEmail(email, password) {
  return createUserWithEmailAndPassword(auth, email, password)
}

export function loginWithEmail(email, password) {
  return signInWithEmailAndPassword(auth, email, password)
}

export function logout() {
  return signOut(auth)
}

export function resetPassword(email) {
  return sendPasswordResetEmail(auth, email)
}
