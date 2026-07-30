import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import LoginPage from './LoginPageView'
import { getBootstrapStatus, login } from '../../../../api'

const navigate = vi.fn()
const toastSuccess = vi.fn()
const toastError = vi.fn()

vi.mock('react-router', async () => {
  const actual = await vi.importActual<typeof import('react-router')>('react-router')
  return {
    ...actual,
    useNavigate: () => navigate,
  }
})

vi.mock('../../../../api', () => ({
  confirmPasswordReset: vi.fn().mockResolvedValue(undefined),
  getBootstrapStatus: vi
    .fn()
    .mockResolvedValue({ admin_username: 'root', needs_password_setup: true }),
  login: vi.fn().mockResolvedValue(undefined),
  requestPasswordReset: vi.fn().mockResolvedValue({ ok: true, reset_token: null }),
  requestRegistration: vi.fn().mockResolvedValue({ id: 'r1' }),
  setupAdminPassword: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../../../shared/forms/useUnsavedChangesWarning', () => ({
  useUnsavedChangesWarning: vi.fn(),
}))

vi.mock('../../../../shared/ui/toast/ToastProvider', () => ({
  useToast: () => ({ success: toastSuccess, error: toastError }),
}))

describe('LoginPageView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    sessionStorage.clear()
  })

  it('supports registration, reset and login flows', async () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: 'Registrieren' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Registrieren' }))
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'new-user' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } })
    fireEvent.change(screen.getByLabelText('Password wiederholen'), {
      target: { value: 'secret123' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Anfrage senden' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Registrierungsanfrage gesendet'))

    fireEvent.click(screen.getByRole('button', { name: 'Passwort-Reset' }))
    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'temp1234' } })
    fireEvent.change(screen.getByLabelText('Password wiederholen'), {
      target: { value: 'temp1234' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reset anfordern' }))
    await waitFor(() =>
      expect(
        screen.getByText('Falls der Benutzer existiert, wurde ein Reset ausgelöst.')
      ).toBeInTheDocument()
    )

    fireEvent.change(screen.getByLabelText('Reset-Token (optional für Bestätigung)'), {
      target: { value: 'token-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Passwort setzen' }))
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Passwort wurde zurückgesetzt'))

    fireEvent.click(screen.getAllByRole('button', { name: 'Login' })[0])
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Login' })[1])
    await waitFor(() => expect(toastSuccess).toHaveBeenCalledWith('Login erfolgreich'))

    expect(navigate).toHaveBeenCalled()
  })

  it('reports when login cancels a scheduled account deletion', async () => {
    vi.mocked(login).mockResolvedValueOnce({ account_deletion_canceled: true })

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: 'alice' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret123' } })
    fireEvent.click(screen.getAllByRole('button', { name: 'Login' })[1])

    await waitFor(() =>
      expect(toastSuccess).toHaveBeenCalledWith(
        'Die geplante Account-Löschung wurde durch deine Anmeldung abgebrochen.'
      )
    )
    expect(navigate).toHaveBeenCalledWith('/')
  })

  it('shows bootstrap setup mode when a token exists', async () => {
    sessionStorage.setItem('bootstrap_token', 'bootstrap-1')

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    await waitFor(() => expect(screen.getByText(/Erststart: Admin-Passwort/)).toBeInTheDocument())
    expect(screen.getByDisplayValue('root')).toBeInTheDocument()
  })

  it('keeps the bootstrap token when its status cannot be checked temporarily', async () => {
    sessionStorage.setItem('bootstrap_token', 'bootstrap-1')
    vi.mocked(getBootstrapStatus).mockRejectedValueOnce(new Error('Backend unavailable'))

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument()
    expect(sessionStorage.getItem('bootstrap_token')).toBe('bootstrap-1')
    expect(screen.getByLabelText('Bootstrap-Token (nur Erstsetup)')).toHaveValue('bootstrap-1')
  })

  it('reveals password text only after using the eye toggle', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    const passwordInput = screen.getByLabelText('Password') as HTMLInputElement
    expect(screen.queryByRole('button', { name: 'Passwort anzeigen' })).not.toBeInTheDocument()

    fireEvent.change(passwordInput, { target: { value: 'secret123' } })
    expect(passwordInput.type).toBe('password')

    fireEvent.click(screen.getByRole('button', { name: 'Passwort anzeigen' }))
    expect(passwordInput.type).toBe('text')
    expect(screen.getByRole('button', { name: 'Passwort verbergen' })).toBeInTheDocument()
  })

  it('keeps bootstrap token hidden until requested and removes setup after completion', async () => {
    ;(getBootstrapStatus as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      admin_username: 'root',
      needs_password_setup: false,
    })

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )

    expect(screen.queryByLabelText('Bootstrap-Token (nur Erstsetup)')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Erstsetup' }))
    fireEvent.change(screen.getByLabelText('Bootstrap-Token (nur Erstsetup)'), {
      target: { value: 'bootstrap-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Erstsetup prüfen' }))

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Erstsetup' })).not.toBeInTheDocument()
    )
    expect(screen.queryByLabelText('Bootstrap-Token (nur Erstsetup)')).not.toBeInTheDocument()
    expect(sessionStorage.getItem('bootstrap_token')).toBeNull()
  })
})
