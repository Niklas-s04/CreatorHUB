import { fireEvent, screen, waitFor } from '@testing-library/react'

import { renderWithRouter } from '../test/render'
import Sidebar from './Sidebar'
import { logout } from '../api'

vi.mock('../api', () => ({
  logout: vi.fn(),
}))

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { href: '' },
    })
  })

  it('zeigt gemeinsame Navigationseinträge', () => {
    renderWithRouter(<Sidebar />)

    expect(screen.getByText('Dashboard')).toBeInTheDocument()
    expect(screen.getByText('Produkte')).toBeInTheDocument()
    expect(screen.getByText('Einstellungen')).toBeInTheDocument()
  })

  it('führt Logout-Aktion aus', async () => {
    ;(logout as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(undefined)

    renderWithRouter(<Sidebar />)
    fireEvent.click(screen.getByRole('button', { name: 'Logout' }))

    await waitFor(() => {
      expect(logout).toHaveBeenCalledTimes(1)
    })
  })

  it('ruft onNavigate bei Link-Klick auf', () => {
    const onNavigate = vi.fn()
    renderWithRouter(<Sidebar onNavigate={onNavigate} />)

    fireEvent.click(screen.getByText('Assets'))
    expect(onNavigate).toHaveBeenCalledTimes(1)
  })
})
