import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import type { ProductDetailVm } from '../../../../shared/api/contracts'
import ProductDetailPageView from './ProductDetailPageView'

const mocks = vi.hoisted(() => ({
  product: null as ProductDetailVm | null,
  apiFetch: vi.fn(),
  refetchProduct: vi.fn(),
  refetchAssets: vi.fn(),
  refetchTransactions: vi.fn(),
}))

vi.mock('../../../../api', () => ({
  apiFetch: mocks.apiFetch,
}))

vi.mock('../../../../shared/api/queries/products', () => ({
  useProductDetailQuery: () => ({
    data: mocks.product,
    isLoading: false,
    refetch: mocks.refetchProduct,
  }),
  useProductAssetsQuery: () => ({
    data: [],
    refetch: mocks.refetchAssets,
  }),
  useProductTransactionsQuery: () => ({
    data: [],
    refetch: mocks.refetchTransactions,
  }),
  useReviewAssetMutation: () => ({ mutateAsync: vi.fn() }),
  useSetPrimaryAssetMutation: () => ({ mutateAsync: vi.fn() }),
}))

vi.mock('../../../../shared/hooks/useAuthz', () => ({
  useAuthz: () => ({
    hasPermission: (permission: string) =>
      ['product.write', 'content.read', 'content.manage'].includes(permission),
  }),
}))

vi.mock('../../../../shared/i18n/i18n', () => ({
  useI18n: () => ({ language: 'en' }),
}))

vi.mock('./useThumb', () => ({
  useThumb: () => null,
}))

function productFixture(overrides: Partial<ProductDetailVm> = {}): ProductDetailVm {
  return {
    id: 'product-1',
    title: 'Camera',
    brand: 'Acme',
    model: 'Pro',
    category: 'Video',
    status: 'active',
    condition: 'very_good',
    purchasePrice: 1299.5,
    purchaseDate: '2024-02-03',
    currentValue: 999,
    currency: 'USD',
    storageLocation: 'Studio A',
    serialNumber: 'SERIAL-42',
    quantity: 2,
    notes: 'Keep dry',
    workflowStatus: 'draft',
    reviewReason: '',
    projectIds: [],
    statusChangedAt: '2024-02-03T12:00:00Z',
    reviewedById: '',
    reviewedByName: '',
    reviewedAt: '',
    createdAt: '2024-02-03T12:00:00Z',
    updatedAt: '2024-02-04T12:00:00Z',
    ...overrides,
  }
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/products/product-1']}>
      <Routes>
        <Route path="/products/:id" element={<ProductDetailPageView />} />
      </Routes>
    </MemoryRouter>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.product = productFixture()
  mocks.refetchProduct.mockResolvedValue({ data: mocks.product })
  mocks.refetchAssets.mockResolvedValue({ data: [] })
  mocks.refetchTransactions.mockResolvedValue({ data: [] })
  mocks.apiFetch.mockImplementation(async (path: string) => {
    if (path.endsWith('/value_history')) return []
    if (path.startsWith('/content/items')) return { items: [] }
    return {}
  })
  Object.defineProperty(window, 'requestIdleCallback', {
    configurable: true,
    value: (callback: () => void) => {
      callback()
      return 1
    },
  })
})

afterEach(() => {
  Reflect.deleteProperty(window, 'requestIdleCallback')
})

describe('ProductDetailPageView', () => {
  it('initializes master data and sends a title-only PATCH', async () => {
    renderPage()

    const title = await screen.findByLabelText('Title')
    await waitFor(() => expect(title).toHaveValue('Camera'))
    expect(screen.getByDisplayValue('Video')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Studio A')).toBeInTheDocument()
    expect(screen.getByDisplayValue('SERIAL-42')).toBeInTheDocument()
    expect(screen.getByDisplayValue('1299.5')).toBeInTheDocument()
    expect(screen.getByDisplayValue('2024-02-03')).toBeInTheDocument()
    expect(screen.getByDisplayValue('USD')).toBeInTheDocument()

    fireEvent.change(title, { target: { value: 'Camera Mark II' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save master data' }))

    await waitFor(() => {
      const saveCall = mocks.apiFetch.mock.calls.find(
        ([path, options]) => path === '/products/product-1' && options?.method === 'PATCH'
      )
      expect(saveCall).toBeDefined()
      expect(JSON.parse(String(saveCall?.[1]?.body))).toEqual({ title: 'Camera Mark II' })
    })
  })

  it('keeps dirty master data when the product query refetches', async () => {
    const view = renderPage()
    const title = await screen.findByLabelText('Title')
    await waitFor(() => expect(title).toHaveValue('Camera'))

    fireEvent.change(title, { target: { value: 'Unsaved local title' } })
    mocks.product = productFixture({
      title: 'New server title',
      updatedAt: '2024-02-05T12:00:00Z',
    })
    view.rerender(
      <MemoryRouter initialEntries={['/products/product-1']}>
        <Routes>
          <Route path="/products/:id" element={<ProductDetailPageView />} />
        </Routes>
      </MemoryRouter>
    )

    expect(screen.getByLabelText('Title')).toHaveValue('Unsaved local title')
  })

  it('keeps a pending status selection while master data becomes dirty', async () => {
    renderPage()
    const title = await screen.findByLabelText('Title')
    await waitFor(() => expect(title).toHaveValue('Camera'))

    const statusSelect = screen.getByDisplayValue('active')
    fireEvent.change(statusSelect, { target: { value: 'sold' } })
    fireEvent.change(title, { target: { value: 'Camera Mark II' } })

    expect(statusSelect).toHaveValue('sold')
  })

  it('moves the quick action to the content reference input', async () => {
    const { container } = renderPage()
    await screen.findByLabelText('Title')
    const contentInput = container.querySelector<HTMLInputElement>('section#content input')
    expect(contentInput).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Prepare content reference' }))

    expect(contentInput).toHaveFocus()
  })
})
