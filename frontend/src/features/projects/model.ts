export type ProjectStatus = 'idea' | 'planning' | 'active' | 'on_hold' | 'completed' | 'archived'
export type ProjectPriority = 'low' | 'medium' | 'high' | 'critical'
export type PreviewStatus =
  | 'not_required'
  | 'pending'
  | 'requested'
  | 'changes_requested'
  | 'approved'

export type ProjectCategory = {
  id: string
  name: string
  color: string
  description: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export type ProjectContent = {
  id: string
  title: string | null
  platform: string
  type: string
  status: string
  planned_date: string | null
  publish_date: string | null
  readiness_score: number
}

export type ProjectProduct = {
  id: string
  title: string
  brand: string | null
  model: string | null
  category: string | null
  status: string
}

export type Project = {
  id: string
  title: string
  category_id: string | null
  category: ProjectCategory | null
  status: ProjectStatus
  priority: ProjectPriority
  owner_user_id: string | null
  owner_name: string | null
  goal: string | null
  brief_md: string | null
  requirements_md: string | null
  notes_md: string | null
  start_date: string | null
  due_date: string | null
  publish_date: string | null
  progress_percent: number
  preview_required: boolean
  preview_status: PreviewStatus
  preview_due_date: string | null
  preview_notes: string | null
  content_count: number
  product_count: number
  overdue: boolean
  preview_attention_required: boolean
  content_items?: ProjectContent[]
  products?: ProjectProduct[]
  created_at: string
  updated_at: string
}

export type Page<T> = {
  items: T[]
  meta: {
    limit: number
    offset: number
    total: number
    sort_by: string
    sort_order: 'asc' | 'desc'
  }
}

export type ContentOption = ProjectContent & { project_ids?: string[] }
export type ProductOption = ProjectProduct & { project_ids?: string[] }

export const PROJECT_STATUSES: ProjectStatus[] = [
  'idea',
  'planning',
  'active',
  'on_hold',
  'completed',
  'archived',
]
export const PROJECT_PRIORITIES: ProjectPriority[] = ['low', 'medium', 'high', 'critical']
export const PREVIEW_STATUSES: PreviewStatus[] = [
  'pending',
  'requested',
  'changes_requested',
  'approved',
]
