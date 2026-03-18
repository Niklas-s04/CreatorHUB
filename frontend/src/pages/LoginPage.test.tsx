import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import LoginPage from './LoginPage'

const navigateMock = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigateMock,
  }
})

vi.mock('../api', () => ({
  confirmPasswordReset: vi.fn(),
  getBootstrapStatus: vi.fn(),
  login: vi.fn(),
  requestPasswordReset: vi.fn(),
  requestRegistration: vi.fn(),
  setupAdminPassword: vi.fn(),
}))

import { login, requestRegistration } from '../api'

function renderPage() {
  return render(<LoginPage />)
}

function getSubmitButton() {
  return screen.getAllByRole('button', { name: 'Login' })[1]
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('validiert Passwortabgleich bei Registrierung', async () => {
    ;(requestRegistration as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({ id: 'x', username: 'u', status: 'pending' })

    renderPage()

    fireEvent.click(screen.getByRole('button', { name: 'Registrieren' }))

    const passwordInputs = document.querySelectorAll('input[type="password"]')
    fireEvent.change(passwordInputs[0], { target: { value: 'Strong!Pass123' } })
    fireEvent.change(passwordInputs[1], { target: { value: 'Different!Pass123' } })

    fireEvent.click(screen.getByRole('button', { name: 'Anfrage senden' }))

    await waitFor(() => {
      expect(screen.getByText('Passwörter stimmen nicht überein')).toBeInTheDocument()
    })
    expect(requestRegistration).not.toHaveBeenCalled()
  })

  it('zeigt Ladezustand während Login-Request', async () => {
    ;(login as unknown as ReturnType<typeof vi.fn>).mockImplementation(
      () => new Promise(resolve => setTimeout(resolve, 200))
    )

    renderPage()
    const passwordInput = document.querySelector('input[type="password"]') as HTMLInputElement
    fireEvent.change(passwordInput, { target: { value: 'Strong!Pass123' } })

    fireEvent.click(getSubmitButton())

    const busyButton = await screen.findByRole('button', { name: '...' })
    expect(busyButton).toBeDisabled()
  })

  it('zeigt Fehlerzustand aus API-Detail', async () => {
    ;(login as unknown as ReturnType<typeof vi.fn>).mockRejectedValue(new Error('{"detail":"Ungültige Zugangsdaten"}'))

    renderPage()
    const passwordInput = document.querySelector('input[type="password"]') as HTMLInputElement
    fireEvent.change(passwordInput, { target: { value: 'wrong' } })

    fireEvent.click(getSubmitButton())

    await waitFor(() => {
      expect(screen.getByText('Ungültige Zugangsdaten')).toBeInTheDocument()
    })
  })
})
