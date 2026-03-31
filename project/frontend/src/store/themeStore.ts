import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type ThemeMode = 'light' | 'dark' | 'system'

function getResolved(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  return mode
}

function applyTheme(resolved: 'light' | 'dark') {
  document.documentElement.setAttribute('data-theme', resolved)
}

interface ThemeStore {
  mode: ThemeMode
  setMode: (m: ThemeMode) => void
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      mode: 'dark' as ThemeMode,
      setMode: (mode) => {
        set({ mode })
        applyTheme(getResolved(mode))
      },
    }),
    { name: 'tradeos_theme' }
  )
)

// Initialize on load
const initTheme = () => {
  const stored = localStorage.getItem('tradeos_theme')
  let mode: ThemeMode = 'dark'
  if (stored) {
    try {
      mode = JSON.parse(stored).state?.mode ?? 'dark'
    } catch {
      // ignore parse errors, fall back to dark
    }
  }
  applyTheme(getResolved(mode))

  // Watch system preference changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (useThemeStore.getState().mode === 'system') {
      applyTheme(getResolved('system'))
    }
  })
}

initTheme()
