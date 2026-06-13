import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ProductsListPageView from './ProductsListPageView'

const setSearchParams = vi.fn()
const navigate = vi.fn()
const invalidateQueries = vi.fn()
const prefetchQuery = vi.fn()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => navigate,
    useSearchParams: () => [new URLSearchParams('q=cam&status=active&limit=25&offset=0&sort_by=updated_at&sort_order=desc'), setSearchParams],
  }
})

vi.mock('../../../../shared/hooks/useAuthz', () => ({
  useAuthz: () => ({ hasPermission: (permission: string) => ['product.read', 'product.write', 'product.export'].includes(permission) }),
}))

vi.mock('../../../../shared/api/queries/products', () => ({
  useCreateProductMutation: () => ({ mutateAsync: vi.fn().mockResolvedValue(undefined), isPending: false }),
  useProductsListQuery: () => ({
    data: {
      items: [
        { id: 'product-1', title: 'Camera', category: 'photo', condition: 'good', status: 'active', currentValue: 99, currency: 'EUR' },
        { id: 'product-2', title: 'Lens', category: 'photo', condition: 'used', status: 'sold', currentValue: 120, currency: 'EUR' },
      ],
      meta: { limit: 25, offset: 0, total: 2, sort_by: 'updated_at', sort_order: 'desc' },
    },
    error: null,
    isFetching: false,
    refetch: vi.fn(),
  }),
}))

vi.mock('../../../../shared/ui/toast/ToastProvider', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}))

vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query')
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries,
      prefetchQuery,
    }),
  }
})

vi.mock('../../../../api', () => ({
  apiFetch: vi.fn().mockResolvedValue(undefined),
  apiUrl: (path: string) => `/api/v1${path}`,
}))

describe('ProductsListPageView', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    vi.spyOn(window, 'open').mockImplementation(() => null)
  })

  it('supports filtering, saving views, exporting and bulk actions', async () => {
    render(
      <MemoryRouter>
        <ProductsListPageView />
      </MemoryRouter>
    )

    expect(screen.getByText('Inventar')).toBeInTheDocument()
    expect(screen.getByText('2 sichtbar · 1-2 von 2')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '+ Produkt' }))
    fireEvent.change(screen.getByPlaceholderText('Titel*'), { target: { value: 'Neues Produkt' } })
    fireEvent.change(screen.getByPlaceholderText('Wert (EUR)'), { target: { value: '12.5' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Speichern' })).toBeEnabled())
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(invalidateQueries).toHaveBeenCalled())

    fireEvent.click(screen.getByLabelText('Produkt Camera auswählen'))
    fireEvent.click(screen.getByRole('button', { name: 'Bulk: Archivieren' }))
    await waitFor(() => expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['products', 'list'] }))

    fireEvent.change(screen.getByLabelText('Produktsuche'), { target: { value: 'kamera' } })
    fireEvent.click(screen.getByRole('button', { name: 'Filter' }))
    expect(setSearchParams).toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))
    expect(setSearchParams).toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Export-Datensatz'), { target: { value: 'transactions' } })
    fireEvent.change(screen.getByLabelText('Export-Jahre'), { target: { value: '2023, 2024' } })
    fireEvent.click(screen.getByRole('button', { name: 'Export CSV' }))
    expect(window.open).toHaveBeenCalled()

    fireEvent.change(screen.getByLabelText('Name für gespeicherte Ansicht'), { target: { value: 'Meine Ansicht' } })
    fireEvent.click(screen.getByRole('button', { name: 'View speichern' }))
    expect(screen.getByText('View löschen: Meine Ansicht')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Spaltenauswahl öffnen'))
    fireEvent.click(screen.getByLabelText('Währung'))
    expect(localStorage.getItem('products.columns.v1')).not.toContain('currency')
  })
})
