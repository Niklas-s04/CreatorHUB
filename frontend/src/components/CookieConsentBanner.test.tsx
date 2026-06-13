import { beforeEach, describe, expect, it } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import CookieConsentBanner from './CookieConsentBanner'

describe('CookieConsentBanner', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('shows when no consent exists and stores analytics consent', () => {
    render(<CookieConsentBanner />)

    expect(
      screen.getByRole('region', { name: /Notwendige Cookies sind erforderlich/i })
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Analytics erlauben/i }))

    expect(window.localStorage.getItem('consent_level')).toBe('all')
    expect(screen.queryByRole('region', { name: /Notwendige Cookies sind erforderlich/i })).toBeNull()
  })

  it('stays hidden after necessary-only consent', () => {
    window.localStorage.setItem('consent_level', 'necessary')

    render(<CookieConsentBanner />)

    expect(screen.queryByRole('region')).toBeNull()
  })
})