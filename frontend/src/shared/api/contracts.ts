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
  workflow_status?: string
  review_reason?: string | null
  source_name?: string | null
  source_url?: string | null
  source_type?: string
  source_review_status?: string
  source_review_note?: string | null
  origin_summary?: string | null
  trust_level?: string
  is_outdated?: boolean
  outdated_reason?: string | null
  outdated_at?: string | null
  current_version?: number
  versions?: KnowledgeDocVersionDto[]
  draft_links?: KnowledgeDocDraftLinkDto[]
}

export type KnowledgeDocVersionDto = {
  id: string
  version_number: number
  title: string
  type: string
  workflow_status: string
  source_review_status: string
  trust_level: string
  is_outdated: boolean
  change_note: string | null
  changed_by_name: string | null
  created_at: string
}

export type KnowledgeDocDraftLinkDto = {
  id: string
  email_draft_id: string
  linked_at: string
  linked_by_name: string | null
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
  workflowStatus: string
  reviewReason: string
  sourceName: string
  sourceUrl: string
  sourceType: string
  sourceReviewStatus: string
  sourceReviewNote: string
  originSummary: string
  trustLevel: string
  isOutdated: boolean
  outdatedReason: string
  outdatedAt: string
  currentVersion: number
  versions: KnowledgeDocVersionVm[]
  draftLinks: KnowledgeDocDraftLinkVm[]
}

export type KnowledgeDocVersionVm = {
  id: string
  versionNumber: number
  title: string
  type: string
  workflowStatus: string
  sourceReviewStatus: string
  trustLevel: string
  isOutdated: boolean
  changeNote: string
  changedByName: string
  createdAt: string
}

export type KnowledgeDocDraftLinkVm = {
  id: string
  emailDraftId: string
  linkedAt: string
  linkedByName: string
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
