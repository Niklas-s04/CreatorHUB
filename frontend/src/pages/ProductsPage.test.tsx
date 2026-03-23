import { fireEvent, screen, waitFor } from '@testing-library/react'

import ProductsPage from './ProductsPage'
import { renderWithRouter } from '../test/render'

vi.mock('../api', () => ({
  apiFetch: vi.fn(),
  getMe: vi.fn(),
}))

import { apiFetch, getMe } from '../api'

describe('ProductsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(getMe as unknown as ReturnType<typeof vi.fn>).mockResolvedValue({
      id: 'u1',
      username: 'editor',
      role: 'editor',
      is_active: true,
      needs_password_setup: false,
      permissions: ['product.read', 'product.write', 'product.export'],
    })
  })

  it('zeigt leeren Zustand ohne Treffer', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([])

    renderWithRouter(<ProductsPage />)

    expect(await screen.findByText('Keine Treffer.')).toBeInTheDocument()
  })

  it('zeigt Fehlerzustand bei Ladefehler', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Laden fehlgeschlagen'))

    renderWithRouter(<ProductsPage />)

    expect(await screen.findByText('Laden fehlgeschlagen')).toBeInTheDocument()
  })

  it('validiert Pflichtfeld im Produktformular über disabled Aktion', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([])

    renderWithRouter(<ProductsPage />)

    fireEvent.click(await screen.findByRole('button', { name: '+ Produkt' }))

    const saveButton = screen.getByRole('button', { name: 'Speichern' })
    expect(saveButton).toBeDisabled()

    fireEvent.change(screen.getByPlaceholderText('Titel*'), { target: { value: 'Neue Kamera' } })
    expect(saveButton).toBeEnabled()
  })

  it('triggert Filter-Ladevorgang über Aktion', async () => {
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([])

    renderWithRouter(<ProductsPage />)

    fireEvent.click(await screen.findByRole('button', { name: 'Filter' }))

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledTimes(2)
    })
  })
})
