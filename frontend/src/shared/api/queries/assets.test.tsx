import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../../api'
import { useAssetLibraryQuery } from './assets'

vi.mock('../../../api', () => ({
  apiFetch: vi.fn(),
}))

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  }
}

describe('useAssetLibraryQuery', () => {
  it('keeps the backend page contract intact', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    vi.mocked(apiFetch).mockResolvedValueOnce({
      meta: { limit: 24, offset: 0, total: 1, sort_by: 'created_at', sort_order: 'desc' },
      items: [
        {
          id: 'asset-1',
          owner_type: 'product',
          owner_id: 'product-1',
          kind: 'image',
          source: 'upload',
          title: 'Image',
          license_type: null,
          license_url: null,
          attribution: null,
          source_name: null,
          source_url: null,
          review_state: 'quarantine',
          is_primary: false,
          url: null,
          width: null,
          height: null,
          size_bytes: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
    })

    const result = renderHook(
      () =>
        useAssetLibraryQuery({
          approvedOnly: false,
          primaryOnly: false,
          licenseFilter: 'any',
        }),
      { wrapper: createWrapper(queryClient) }
    )

    await waitFor(() => expect(result.result.current.isSuccess).toBe(true))

    expect(result.result.current.data?.meta.total).toBe(1)
    expect(result.result.current.data?.items[0]?.review_state).toBe('quarantine')
    expect(apiFetch).toHaveBeenCalledWith(
      '/assets/library?approved_only=false&primary_only=false&license_filter=any&limit=24&offset=0'
    )
  })
})
