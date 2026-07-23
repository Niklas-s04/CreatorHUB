import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import {
  useChangeProductStatusMutation,
  useCreateProductMutation,
  useProductAssetsQuery,
  useProductDetailQuery,
  useProductTransactionsQuery,
  useProductsListQuery,
  useReviewAssetMutation,
  useSetPrimaryAssetMutation,
  useUpdateProductNotesMutation,
} from './products'

vi.mock('../../../api', () => ({
  apiFetch: vi.fn(),
}))

import { apiFetch } from '../../../api'

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
}

describe('products queries and mutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('parses product list responses from arrays and object pages', async () => {
    const queryClient = createQueryClient()
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce([
        {
          id: 'product-1',
          title: 'Camera',
          status: 'active',
          current_value: 99,
          currency: 'EUR',
          category: null,
          condition: null,
        },
        {
          id: '',
          title: null,
          status: 'active',
          current_value: null,
          currency: null,
          category: null,
          condition: null,
        },
      ])
      .mockResolvedValueOnce({
        items: [
          {
            id: 'product-2',
            title: 'Lens',
            status: 'sold',
            current_value: 120,
            currency: null,
            category: null,
            condition: null,
          },
        ],
        meta: { limit: 25, offset: 5, total: 1, sort_by: 'title', sort_order: 'asc' },
      })

    const first = renderHook(() => useProductsListQuery({ limit: 10, offset: 2 }), {
      wrapper: createWrapper(queryClient),
    })
    await waitFor(() => expect(first.result.current.isSuccess).toBe(true))
    expect(first.result.current.data?.items).toHaveLength(1)
    expect(first.result.current.data?.meta).toMatchObject({
      limit: 10,
      offset: 2,
      total: 2,
      sort_by: 'updated_at',
      sort_order: 'desc',
    })

    const second = renderHook(() => useProductsListQuery({ q: 'lens', sort_order: 'asc' }), {
      wrapper: createWrapper(queryClient),
    })
    await waitFor(() => expect(second.result.current.isSuccess).toBe(true))
    expect(second.result.current.data?.meta).toMatchObject({
      limit: 25,
      offset: 5,
      total: 1,
      sort_by: 'title',
      sort_order: 'asc',
    })
    expect(second.result.current.data?.items[0]?.title).toBe('Lens')
  })

  it('loads product detail, assets and transactions', async () => {
    const queryClient = createQueryClient()
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>)
      .mockResolvedValueOnce({
        id: 'product-7',
        title: 'Camera',
        status: 'active',
        current_value: 99,
        currency: 'EUR',
        notes_md: 'hello',
      })
      .mockResolvedValueOnce([
        {
          id: 'asset-11',
          title: 'Image',
          source: 'upload',
          review_state: 'approved',
          is_primary: true,
        },
      ])
      .mockResolvedValueOnce([
        {
          id: 'tx-21',
          product_id: '7',
          type: 'buy',
          date: '2024-01-01',
          amount: 42,
          currency: 'EUR',
          counterparty: null,
          notes: null,
        },
      ])

    const detail = renderHook(() => useProductDetailQuery('7'), {
      wrapper: createWrapper(queryClient),
    })
    const assets = renderHook(() => useProductAssetsQuery('7'), {
      wrapper: createWrapper(queryClient),
    })
    const transactions = renderHook(() => useProductTransactionsQuery('7'), {
      wrapper: createWrapper(queryClient),
    })

    await waitFor(() => expect(detail.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(assets.result.current.isSuccess).toBe(true))
    await waitFor(() => expect(transactions.result.current.isSuccess).toBe(true))

    expect(detail.result.current.data?.title).toBe('Camera')
    expect(assets.result.current.data?.[0]?.isPrimary).toBe(true)
    expect(transactions.result.current.data?.[0]?.amount).toBe(42)
  })

  it('updates notes with optimistic rollback on failure', async () => {
    const queryClient = createQueryClient()
    const cancelQueries = vi.spyOn(queryClient, 'cancelQueries')
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    const getQueryData = vi.spyOn(queryClient, 'getQueryData').mockReturnValue({
      id: 'product-7',
      title: 'Camera',
      brand: '',
      model: '',
      status: 'active',
      condition: '',
      currentValue: 99,
      currency: '',
      notes: 'old',
    })
    const setQueryData = vi.spyOn(queryClient, 'setQueryData')
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('offline'))

    const { result } = renderHook(() => useUpdateProductNotesMutation(), {
      wrapper: createWrapper(queryClient),
    })

    await act(async () => {
      await expect(result.current.mutateAsync({ id: '7', notes_md: 'new' })).rejects.toThrow(
        'offline'
      )
    })

    expect(cancelQueries).toHaveBeenCalledWith({ queryKey: ['products', 'detail', '7'] })
    expect(getQueryData).toHaveBeenCalled()
    expect(setQueryData).toHaveBeenCalled()
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['products', 'detail', '7'] })
  })

  it('invalidates product data after mutation actions', async () => {
    const queryClient = createQueryClient()
    const invalidateQueries = vi.spyOn(queryClient, 'invalidateQueries')
    ;(apiFetch as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(undefined)

    const createHook = renderHook(() => useCreateProductMutation(), {
      wrapper: createWrapper(queryClient),
    })
    await act(async () => {
      await createHook.result.current.mutateAsync({ title: 'New item' })
    })

    const statusHook = renderHook(() => useChangeProductStatusMutation(), {
      wrapper: createWrapper(queryClient),
    })
    await act(async () => {
      await statusHook.result.current.mutateAsync({
        id: '7',
        status: 'sold',
        date: '2024-01-01',
        amount: 10,
      })
    })

    const reviewHook = renderHook(() => useReviewAssetMutation('7'), {
      wrapper: createWrapper(queryClient),
    })
    await act(async () => {
      await reviewHook.result.current.mutateAsync({ assetId: 'asset-11', state: 'approved' })
    })

    const primaryHook = renderHook(() => useSetPrimaryAssetMutation('7'), {
      wrapper: createWrapper(queryClient),
    })
    await act(async () => {
      await primaryHook.result.current.mutateAsync({ assetId: 'asset-11' })
    })

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['products', 'list'] })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['products', 'detail', '7'] })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['products', 'transactions', '7'] })
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ['products', 'assets', '7'] })
  })
})
