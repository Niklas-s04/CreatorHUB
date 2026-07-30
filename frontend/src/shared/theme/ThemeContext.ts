import { createContext, useContext } from 'react'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'creatorhub.theme.v1'

export type ThemeContextValue = {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

export const ThemeContext = createContext<ThemeContextValue>({
  theme: 'dark',
  setTheme: () => undefined,
  toggleTheme: () => undefined,
})

export function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'dark'

  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'light' ? 'light' : 'dark'
  } catch {
    return 'dark'
  }
}

export function applyTheme(theme: Theme): void {
  if (typeof document === 'undefined') return
  document.documentElement.dataset.theme = theme
  document.documentElement.style.colorScheme = theme
}

export function initializeTheme(): Theme {
  const theme = getInitialTheme()
  applyTheme(theme)
  return theme
}

export function persistTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, theme)
  } catch {
    // The selected theme still applies when storage is unavailable.
  }
}

export function useTheme(): ThemeContextValue {
  return useContext(ThemeContext)
}
