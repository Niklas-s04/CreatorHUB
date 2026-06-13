import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import SettingsAccountPageView from './SettingsAccountPageView'
import { revokeSession } from '../../../../api'

const navigate = vi.fn()
const toastSuccess = vi.fn()
const toastError = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

vi.mock('../../../../api', () => ({
  apiFetch: vi.fn().mockImplementation(async (path: string) => {
    if (path === '/knowledge') return []
    throw new Error(`Unexpected apiFetch path: ${path}`)
  }),
  changePassword: vi.fn().mockResolvedValue(undefined),
  deleteAccount: vi.fn().mockResolvedValue({ ok: 'true', message: 'Account scheduled for deletion.' }),
  disableMfa: vi.fn().mockResolvedValue({ enabled: false }),
  enableMfa: vi.fn().mockResolvedValue({ recovery_codes: [] }),
  getLoginHistory: vi.fn().mockResolvedValue([]),
  getMfaStatus: vi.fn().mockResolvedValue({ enabled: false }),
  getMySessions: vi.fn().mockResolvedValue([]),
  provisionMfa: vi.fn().mockResolvedValue({ secret: 'SECRET', otpauth_uri: 'otpauth://totp/test' }),
  revokeSession: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../../../shared/forms/useUnsavedChangesWarning', () => ({
  useUnsavedChangesWarning: vi.fn(),
}))

vi.mock('../../../../shared/ui/toast/ToastProvider', () => ({
  useToast: () => ({ success: toastSuccess, error: toastError }),
}))

describe('SettingsAccountPageView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders and submits the account deletion flow', async () => {
    render(
      <MemoryRouter>
        <SettingsAccountPageView />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('Account löschen')).toBeInTheDocument())

    fireEvent.change(screen.getByLabelText('Bestätigung'), { target: { value: 'LÖSCHEN' } })
    fireEvent.click(screen.getByRole('button', { name: 'Account zur Löschung anmelden' }))

    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Account scheduled for deletion.'))
    expect(navigate).toHaveBeenCalledWith('/login')
  })

  it('renders sessions and login history and allows revoking another session', async () => {
    vi.mocked(revokeSession).mockResolvedValueOnce(undefined)

    const api = await import('../../../../api')
    vi.mocked(api.getMySessions).mockResolvedValueOnce([
      {
        id: 's-current',
        created_at: '2024-01-01T00:00:00Z',
        last_activity_at: '2024-01-02T00:00:00Z',
        expires_at: '2024-02-01T00:00:00Z',
        idle_expires_at: '2024-01-02T01:00:00Z',
        ip_address: '127.0.0.1',
        device_label: 'Current Device',
        user_agent: null,
        mfa_verified: true,
        mfa_step_up_expires_at: '2024-01-02T00:05:00Z',
        is_current: true,
      },
      {
        id: 's-other',
        created_at: '2024-01-01T00:00:00Z',
        last_activity_at: '2024-01-02T00:00:00Z',
        expires_at: '2024-02-01T00:00:00Z',
        idle_expires_at: '2024-01-02T01:00:00Z',
        ip_address: '10.0.0.2',
        device_label: 'Other Device',
        user_agent: null,
        mfa_verified: false,
        mfa_step_up_expires_at: null,
        is_current: false,
      },
    ])
    vi.mocked(api.getLoginHistory).mockResolvedValueOnce([
      {
        id: 'h1',
        username: 'alice',
        occurred_at: '2024-01-02T00:00:00Z',
        ip_address: '127.0.0.1',
        user_agent: 'UA',
        success: true,
        suspicious: false,
        reason: null,
      },
    ])

    render(
      <MemoryRouter>
        <SettingsAccountPageView />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText('Aktive Sessions')).toBeInTheDocument())
    expect(screen.getByRole('heading', { name: 'Anmeldehistorie' })).toBeInTheDocument()
    expect(screen.getByText(/Current Device/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Session auf Other Device beenden/i }))
    await waitFor(() => expect(revokeSession).toHaveBeenCalledWith('s-other'))
  })
})
