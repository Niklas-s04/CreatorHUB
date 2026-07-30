import { fireEvent, render, screen } from '@testing-library/react'

import { useTheme } from './ThemeContext'
import { ThemeProvider } from './ThemeProvider'

function ThemeProbe() {
  const { theme, toggleTheme } = useTheme()
  return (
    <button type="button" onClick={toggleTheme}>
      {theme}
    </button>
  )
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    delete document.documentElement.dataset.theme
    document.documentElement.style.colorScheme = ''
  })

  it('verwendet Dark Mode als Standard', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    )

    expect(screen.getByRole('button', { name: 'dark' })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(window.localStorage.getItem('creatorhub.theme.v1')).toBe('dark')
  })

  it('schaltet auf Light Mode um und speichert die Auswahl', () => {
    render(
      <ThemeProvider>
        <ThemeProbe />
      </ThemeProvider>
    )

    fireEvent.click(screen.getByRole('button', { name: 'dark' }))

    expect(screen.getByRole('button', { name: 'light' })).toBeInTheDocument()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem('creatorhub.theme.v1')).toBe('light')
  })
})
