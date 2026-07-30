import type { ReactNode } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const mocks = vi.hoisted(() => ({
  checkSession: vi.fn(),
}))

vi.mock('./api', () => ({
  checkSession: mocks.checkSession,
}))

vi.mock('./components/TopBar', () => ({
  default: () => null,
}))

vi.mock('./components/Sidebar', () => ({
  default: () => null,
}))

vi.mock('./components/CookieConsentBanner', () => ({
  default: () => null,
}))

vi.mock('./shared/ui/navigation/Breadcrumbs', () => ({
  Breadcrumbs: () => null,
}))

vi.mock('./shared/auth/StepUpProvider', () => ({
  StepUpProvider: ({ children }: { children: ReactNode }) => children,
}))

vi.mock('./pages/EmailPage', () => ({
  default: () => <div>Email workspace</div>,
}))

function CurrentPath() {
  return <output aria-label="current-path">{useLocation().pathname}</output>
}

describe('App routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.checkSession.mockResolvedValue(true)
  })

  it('redirects legacy deal links to the existing email deal workspace', async () => {
    render(
      <MemoryRouter initialEntries={['/deals']}>
        <App />
        <CurrentPath />
      </MemoryRouter>
    )

    expect(await screen.findByText('Email workspace')).toBeInTheDocument()
    expect(screen.getByLabelText('current-path')).toHaveTextContent('/email')
  })

  it('shows a retryable error when the session endpoint is temporarily unavailable', async () => {
    const user = userEvent.setup()
    mocks.checkSession.mockReset()
    mocks.checkSession.mockRejectedValueOnce(new Error('backend unavailable'))
    mocks.checkSession.mockResolvedValueOnce(true)

    render(
      <MemoryRouter initialEntries={['/deals']}>
        <App />
      </MemoryRouter>
    )

    expect(
      await screen.findByText('Die Sitzung konnte nicht geprüft werden. Bitte versuche es erneut.')
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Erneut versuchen' }))

    expect(await screen.findByText('Email workspace')).toBeInTheDocument()
    expect(mocks.checkSession).toHaveBeenCalledTimes(2)
  })
})
