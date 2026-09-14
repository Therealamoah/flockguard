import { create } from 'zustand'

const STORAGE_KEY = 'flockguard-theme'

function systemPrefersDark() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches
}

function initialTheme() {
  if (typeof window === 'undefined') return 'light'
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // localStorage unavailable (private mode, etc.) - fall through to system preference.
  }
  return systemPrefersDark() ? 'dark' : 'light'
}

function applyTheme(theme) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', theme === 'dark')
  try {
    window.localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // Best-effort persistence only.
  }
}

const initial = initialTheme()
applyTheme(initial)

export const useThemeStore = create((set, get) => ({
  theme: initial,
  toggleTheme() {
    const next = get().theme === 'dark' ? 'light' : 'dark'
    applyTheme(next)
    set({ theme: next })
  },
  setTheme(theme) {
    applyTheme(theme)
    set({ theme })
  },
}))
