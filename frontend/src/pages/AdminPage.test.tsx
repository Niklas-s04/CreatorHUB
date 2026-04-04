import { act, fireEvent, screen, waitFor } from '@testing-library/react'

import AdminPage from './AdminPage'
import { renderWithRouter } from '../test/render'

vi.mock('../api', () => ({
  approveRegistrationRequest: vi.fn(),
  apiFetch: vi.fn(),
  getMe: vi.fn(),
  getRegistrationRequests: vi.fn(),
  getUsers: vi.fn(),
  getUserSessions: vi.fn(),
  lockUser: vi.fn(),
  unlockUser: vi.fn(),
  requestAdminPasswordReset: vi.fn(),
}))

import { approveRegistrationRequest, apiFetch, getMe, getRegistrationRequests, getUsers, getUserSessions } from '../api'

describe('AdminPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (url: string) => {
      if (url === '/dashboard/summary') {
        return { metrics: [] }
      }
      if (url.startsWith('/audit?')) {
        return { items: [], meta: { total: 0 } }
      }
      return {}
    })
    ;(getRegistrationRequests as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([])
    ;(getUsers as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([])
    ;(getUserSessions as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([])
  })

  it('zeigt rollenabhängige Sichtbarkeit für Nicht-Admin', async () => {
    ;(getMe as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: 'u1',
      username: 'viewer',
      role: 'viewer',
      is_active: true,
      needs_password_setup: false,
      locked_until: null,
      last_activity_at: null,
      permissions: [],
    })

    renderWithRouter(<AdminPage />)

    expect(await screen.findByText('Nur Admin kann Registrierungsanfragen bearbeiten.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Freigeben' })).not.toBeInTheDocument()
  })

  it('zeigt leere Zustände für Admin ohne Daten', async () => {
    ;(getMe as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        id: 'a1',
        username: 'admin',
        role: 'admin',
        is_active: true,
        needs_password_setup: false,
        locked_until: null,
        last_activity_at: null,
        permissions: ['user.read', 'user.approve_registration'],
      })
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce({ items: [], meta: { total: 0 } })
    ;(getUsers as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([])
    ;(getUserSessions as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([])

    renderWithRouter(<AdminPage />)

    expect(await screen.findByText('Keine Benutzer')).toBeInTheDocument()
    expect(screen.getByText('Keine offenen Anfragen')).toBeInTheDocument()
  })

  it('zeigt Ladezustand beim Initial-Load', async () => {
    let resolveMe: ((value: unknown) => void) | null = null
    const mePromise = new Promise(resolve => {
      resolveMe = resolve
    })
    ;(getMe as unknown as ReturnType<typeof vi.fn>).mockImplementationOnce(() => mePromise)

    renderWithRouter(<AdminPage />)

    const refreshBusy = await screen.findByRole('button', { name: '...' })
    expect(refreshBusy).toBeDisabled()

    await act(async () => {
      resolveMe?.({
        id: 'u1',
        username: 'viewer',
        role: 'viewer',
        is_active: true,
        needs_password_setup: false,
        locked_until: null,
        last_activity_at: null,
        permissions: [],
      })
      await Promise.resolve()
    })
  })

  it('zeigt Fehlerzustand', async () => {
    ;(getMe as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Backend nicht erreichbar'))

    renderWithRouter(<AdminPage />)

    expect(await screen.findByText('Backend nicht erreichbar')).toBeInTheDocument()
  })

  it('führt rollenabhängige Aktion Freigeben aus', async () => {
    ;(getMe as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: 'a1',
      username: 'admin',
      role: 'admin',
      is_active: true,
      needs_password_setup: false,
      locked_until: null,
      last_activity_at: null,
      permissions: ['user.read', 'user.approve_registration'],
    })
    ;(getRegistrationRequests as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (statusFilter?: string) => {
      if (statusFilter === 'pending') {
        return [{ id: 'r1', username: 'new-user', status: 'pending', reviewed_at: null, reviewed_by_user_id: null, reviewed_by_username: null, rejection_reason: null }]
      }
      return [{ id: 'h1', username: 'old-user', status: 'approved', reviewed_at: '2026-04-04T10:00:00Z', reviewed_by_user_id: 'a1', reviewed_by_username: 'admin', rejection_reason: null }]
    })
    ;(getUsers as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([
      {
        id: 'u2',
        username: 'editor',
        role: 'editor',
        is_active: true,
        needs_password_setup: false,
        locked_until: null,
        last_activity_at: null,
        mfa_enabled: false,
        active_sessions: 1,
        permissions: ['content.read'],
      },
    ])
    ;(getUserSessions as unknown as ReturnType<typeof vi.fn>).mockResolvedValue([])
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockImplementation(async (url: string) => {
      if (url === '/dashboard/summary') {
        return { metrics: [] }
      }
      if (url.startsWith('/audit?')) {
        return { items: [], meta: { total: 0 } }
      }
      if (url === '/auth/registration-requests/r1/approve') {
        return {
          id: 'r1',
          username: 'new-user',
          status: 'approved',
          reviewed_at: '2026-04-04T12:00:00Z',
          reviewed_by_user_id: 'a1',
          reviewed_by_username: 'admin',
          rejection_reason: null,
        }
      }
      return {}
    })

    renderWithRouter(<AdminPage />)

    fireEvent.click(await screen.findByRole('button', { name: 'Freigeben' }))

    await waitFor(() => {
      expect(approveRegistrationRequest).toHaveBeenCalledWith('r1')
    })
  })
})
