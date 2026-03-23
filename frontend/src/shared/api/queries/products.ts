import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '../../../api'
import { toProductAssetVm, toProductDetailVm, toProductListItemVm, toProductTransactionVm } from '../mappers'
import type { ProductAssetVm, ProductDetailVm, ProductListItemVm, ProductTransactionVm } from '../contracts'
import { parseProductAssetsDtoArray, parseProductDto, parseProductsDtoArray, parseProductTransactionsDtoArray } from '../validators'
import { queryKeys } from '../queryKeys'

export function useProductsListQuery(params: { q?: string; status?: string; limit?: number }) {
  return useQuery<ProductListItemVm[]>({
    queryKey: queryKeys.products.list(params),
    staleTime: 20_000,
    queryFn: async () => {
      const search = new URLSearchParams()
      search.set('limit', String(params.limit ?? 100))
      if (params.q) search.set('q', params.q)
      if (params.status) search.set('status', params.status)
      const data = await apiFetch<unknown>(`/products?${search.toString()}`)
      return parseProductsDtoArray(data).map(toProductListItemVm).filter(product => product.id >= 0)
    },
  })
}

export function useProductDetailQuery(id: string | undefined) {
  return useQuery<ProductDetailVm>({
    queryKey: queryKeys.products.detail(id || ''),
    enabled: Boolean(id),
    staleTime: 15_000,
    queryFn: async () => {
      const data = await apiFetch<unknown>(`/products/${id}`)
      return toProductDetailVm(parseProductDto(data))
    },
  })
}

export function useProductAssetsQuery(id: string | undefined) {
  return useQuery<ProductAssetVm[]>({
    queryKey: queryKeys.products.assets(id || ''),
    enabled: Boolean(id),
    staleTime: 45_000,
    queryFn: async () => {
      const data = await apiFetch<unknown>(`/assets?owner_type=product&owner_id=${id}&include_pending=true`)
      return parseProductAssetsDtoArray(data).map(toProductAssetVm).filter(asset => asset.id >= 0)
    },
  })
}

export function useProductTransactionsQuery(id: string | undefined) {
  return useQuery<ProductTransactionVm[]>({
    queryKey: queryKeys.products.transactions(id || ''),
    enabled: Boolean(id),
    staleTime: 10_000,
    queryFn: async () => {
      const data = await apiFetch<unknown>(`/products/${id}/transactions`)
      return parseProductTransactionsDtoArray(data).map(toProductTransactionVm).filter(tx => tx.id >= 0)
    },
  })
}

type CreateProductInput = {
  title: string
  brand?: string
  model?: string
  current_value?: number
}

export function useCreateProductMutation(listParams: { q?: string; status?: string; limit?: number }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: CreateProductInput) => {
      await apiFetch('/products', { method: 'POST', body: JSON.stringify(payload) })
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['products', 'list'] })
    },
  })
}

type UpdateNotesInput = { id: string; notes_md: string }

export function useUpdateProductNotesMutation() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, notes_md }: UpdateNotesInput) => {
      await apiFetch(`/products/${id}`, { method: 'PATCH', body: JSON.stringify({ notes_md }) })
      return { id, notes_md }
    },
    onMutate: async ({ id, notes_md }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.products.detail(id) })
      const prev = queryClient.getQueryData<ProductDetailVm>(queryKeys.products.detail(id))
      if (prev) {
        queryClient.setQueryData<ProductDetailVm>(queryKeys.products.detail(id), {
          ...prev,
          notes: notes_md,
        })
      }
      return { prev, id }
    },
    onError: (_error, _vars, context) => {
      if (context?.prev && context.id) {
        queryClient.setQueryData(queryKeys.products.detail(context.id), context.prev)
      }
    },
    onSettled: async (_data, _error, vars) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.products.detail(vars.id) })
    },
  })
}

type ChangeStatusInput = {
  id: string
  status: string
  tx_date: string
  amount: number | null
}

export function useChangeProductStatusMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, status, tx_date, amount }: ChangeStatusInput) => {
      await apiFetch(`/products/${id}/status`, {
        method: 'POST',
        body: JSON.stringify({ status, tx_date, amount }),
      })
      return { id }
    },
    onSuccess: async ({ id }) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.products.detail(id) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.products.transactions(id) }),
        queryClient.invalidateQueries({ queryKey: ['products', 'list'] }),
      ])
    },
  })
}

export function useReviewAssetMutation(id: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ assetId, state }: { assetId: number; state: 'approved' | 'rejected' }) => {
      await apiFetch(`/assets/${assetId}`, { method: 'PATCH', body: JSON.stringify({ review_state: state }) })
    },
    onSuccess: async () => {
      if (!id) return
      await queryClient.invalidateQueries({ queryKey: queryKeys.products.assets(id) })
    },
  })
}

export function useSetPrimaryAssetMutation(id: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ assetId }: { assetId: number }) => {
      await apiFetch(`/assets/${assetId}/primary`, { method: 'POST' })
    },
    onSuccess: async () => {
      if (!id) return
      await queryClient.invalidateQueries({ queryKey: queryKeys.products.assets(id) })
    },
  })
}
