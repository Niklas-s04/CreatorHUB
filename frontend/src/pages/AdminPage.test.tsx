import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'

import AdminPage from './AdminPage'

vi.mock('../api', () => ({
  apiFetch: vi.fn(),
  getUsers: vi.fn(),
}))

import { apiFetch, getUsers } from '../api'

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('zeigt rollenabhängige Sichtbarkeit für Nicht-Admin', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: 'u1',
      username: 'viewer',
      role: 'viewer',
      is_active: true,
      needs_password_setup: false,
    })

    render(<AdminPage />)

    expect(await screen.findByText('Nur Admin kann Registrierungsanfragen bearbeiten.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Freigeben' })).not.toBeInTheDocument()
  })

  it('zeigt leere Zustände für Admin ohne Daten', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        id: 'a1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        needs_password_setup: false,
      })
      .mockResolvedValueOnce([])
    ;(getUsers as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([])

    render(<AdminPage />)

    expect(await screen.findByText('Keine Benutzer.')).toBeInTheDocument()
    expect(screen.getByText('Keine offenen Anfragen.')).toBeInTheDocument()
  })

  it('zeigt Ladezustand beim Initial-Load', async () => {
    let resolveMe: ((value: unknown) => void) | null = null
    const mePromise = new Promise(resolve => {
      resolveMe = resolve
    })
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockImplementationOnce(() => mePromise)

    render(<AdminPage />)

    const refreshBusy = await screen.findByRole('button', { name: '...' })
    expect(refreshBusy).toBeDisabled()

    await act(async () => {
      resolveMe?.({
        id: 'u1',
        username: 'viewer',
        role: 'viewer',
        is_active: true,
        needs_password_setup: false,
      })
      await Promise.resolve()
    })
  })

  it('zeigt Fehlerzustand', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Backend nicht erreichbar'))

    render(<AdminPage />)

    expect(await screen.findByText('Backend nicht erreichbar')).toBeInTheDocument()
  })

  it('führt rollenabhängige Aktion Freigeben aus', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        id: 'a1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        needs_password_setup: false,
      })
      .mockResolvedValueOnce([{ id: 'r1', username: 'new-user', status: 'pending' }])
      .mockResolvedValueOnce({})
      .mockResolvedValueOnce({
        id: 'a1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        needs_password_setup: false,
      })
      .mockResolvedValueOnce([])
    ;(getUsers as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([{ id: 'u2', username: 'editor', role: 'editor', is_active: true, needs_password_setup: false, mfa_enabled: false, active_sessions: 1 }])
      .mockResolvedValueOnce([])

    render(<AdminPage />)

    fireEvent.click(await screen.findByRole('button', { name: 'Freigeben' }))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/auth/registration-requests/r1/approve', { method: 'POST' })
    })
  })
})
