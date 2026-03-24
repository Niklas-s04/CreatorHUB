export type ProductStatusDto = 'active' | 'sold' | 'gifted' | 'returned' | 'broken' | 'archived'

export type ProductDto = {
  id: number
  title: string
  brand: string | null
  model: string | null
  category: string | null
  condition: string | null
  status: ProductStatusDto
  current_value: number | null
  currency: string | null
  quantity: number | null
  notes_md: string | null
  updated_at: string | null
}

export type ProductAssetDto = {
  id: number
  title: string | null
  source: string | null
  review_state: 'pending' | 'approved' | 'rejected'
  is_primary: boolean
  license_type: string | null
  attribution: string | null
  source_url: string | null
  license_url: string | null
}

export type ProductTransactionDto = {
  id: number
  tx_type: string
  tx_date: string | null
  amount: number | null
  currency: string | null
  note: string | null
}

export type KnowledgeDocDto = {
  id: string
  type: string
  title: string
  content: string
}

export type ContentTaskDto = {
  id: number
  title: string
  status: string
  updated_at: string | null
}

export type ImageSearchJobDto = {
  status: 'queued' | 'running' | 'finished' | 'failed'
  result: { query?: string; count?: number; candidates?: unknown[] } | null
  error: string | null
}

export type ProductListItemVm = {
  id: number
  title: string
  category: string
  condition: string
  status: ProductStatusDto
  currentValue: number | null
  currency: string
}

export type ProductDetailVm = {
  id: number
  title: string
  brand: string
  model: string
  status: ProductStatusDto
  condition: string
  currentValue: number | null
  currency: string
  notes: string
}

export type ProductAssetVm = {
  id: number
  title: string
  source: string
  reviewState: 'pending' | 'approved' | 'rejected'
  isPrimary: boolean
  licenseType: string
  attribution: string
  sourceUrl: string
  licenseUrl: string
}

export type ProductTransactionVm = {
  id: number
  txType: string
  txDate: string
  amount: number | null
  currency: string
  note: string
}

export type KnowledgeDocVm = {
  id: string
  type: string
  title: string
  content: string
}

export type DashboardProductVm = {
  id: number
  title: string
  status: ProductStatusDto
  quantity: number
  currentValue: number
  updatedAt: string
}

export type DashboardTaskVm = {
  id: number
  title: string
  status: string
  updatedAt: string
}
