import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '../../../api'
import { queryKeys } from '../queryKeys'

export type AssetOwnerType = 'product' | 'content' | 'email' | 'deal'
export type AssetKind = 'image' | 'pdf' | 'link' | 'video'
export type AssetReviewState = 'pending' | 'approved' | 'rejected'
export type LicenseFilter = 'any' | 'licensed' | 'missing'

export type AssetLibraryItem = {
  id: string
  owner_type: AssetOwnerType
  owner_id: string
  kind: AssetKind
  source: 'upload' | 'web'
  title: string | null
  license_type: string | null
  license_url: string | null
  license_state?: string | null
  attribution: string | null
  source_name: string | null
  source_url: string | null
  review_state: AssetReviewState
  is_primary: boolean
  url: string | null
  width: number | null
  height: number | null
  size_bytes: number | null
  created_at: string
  updated_at: string
}

type AssetLibraryQueryParams = {
  search?: string
  ownerType?: AssetOwnerType
  kind?: AssetKind
  approvedOnly: boolean
  primaryOnly: boolean
  licenseFilter: LicenseFilter
  limit?: number
}

export function useAssetLibraryQuery(params: AssetLibraryQueryParams) {
  const normalizedParams: Record<string, string> = {
    approved_only: params.approvedOnly ? 'true' : 'false',
    primary_only: params.primaryOnly ? 'true' : 'false',
    license_filter: params.licenseFilter,
    limit: String(params.limit ?? 120),
  }
  if (params.search) normalizedParams.search = params.search
  if (params.ownerType) normalizedParams.owner_type = params.ownerType
  if (params.kind) normalizedParams.kind = params.kind

  return useQuery<AssetLibraryItem[]>({
    queryKey: queryKeys.assets.library(normalizedParams),
    staleTime: 30_000,
    queryFn: async () => {
      const search = new URLSearchParams(normalizedParams)
      return apiFetch<AssetLibraryItem[]>(`/assets/library?${search.toString()}`)
    },
  })
}
