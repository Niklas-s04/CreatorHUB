export type ApiPage<T> = { items: T[] }

export type ContentStatus = 'idea' | 'draft' | 'recorded' | 'edited' | 'scheduled' | 'published'
export type ContentTaskStatus = 'todo' | 'doing' | 'done'
export type ContentTaskType =
  | 'script'
  | 'record'
  | 'edit'
  | 'thumbnail'
  | 'upload'
  | 'seo'
  | 'crosspost'
  | 'design'
  | 'publish'
export type ContentTaskPriority = 'low' | 'medium' | 'high' | 'critical'
export type ChecklistPhase = 'pre_production' | 'production' | 'post_production' | 'upload'

export type PlatformField = {
  key?: string
  label?: string
  type?: 'text' | 'textarea' | 'date' | 'url' | 'number' | 'checkbox' | 'select' | 'tags'
  required?: boolean
  placeholder?: string
  help_text?: string
  options?: string[]
}

export type PlatformSchema = {
  required_base_fields?: string[]
  fields?: PlatformField[]
}

export type ContentItem = {
  id: string
  product_id?: string | null
  title: string | null
  hook?: string | null
  script_md?: string | null
  description_md?: string | null
  tags_csv?: string | null
  platform: string
  type: string
  status: ContentStatus
  planned_date?: string | null
  publish_date?: string | null
  external_url?: string | null
  platform_meta_json: Record<string, string | number | boolean | null>
  readiness_score: number
}

export type ContentTask = {
  id: string
  content_item_id: string
  type: ContentTaskType
  title: string | null
  status: ContentTaskStatus
  priority: ContentTaskPriority
  due_date?: string | null
  required_for_publish: boolean
  can_block_publish: boolean
  notes?: string | null
}

export type PlanningView = {
  item: ContentItem
  tasks: ContentTask[]
  open_task_count: number
  required_open_count: number
  readiness_score: number
  publish_ready: boolean
  blockers: string[]
}

export type PlatformProfile = {
  id: string
  platform: string
  name: string
  schema_json: PlatformSchema
  is_active: boolean
  is_system: boolean
  version: number
}

export type ChecklistTemplateItem = {
  id?: string
  title: string
  phase: ChecklistPhase
  required: boolean
  priority_default: ContentTaskPriority
  due_offset_days: number | null
  can_block_publish: boolean
  sort_order: number
}

export type ChecklistTemplate = {
  id: string
  name: string
  description?: string | null
  applies_to_platform: string | null
  applies_to_type: string | null
  is_shared: boolean
  is_system: boolean
  version: number
  items: ChecklistTemplateItem[]
}

export const STATUS_COLUMNS: ContentStatus[] = [
  'idea',
  'draft',
  'recorded',
  'edited',
  'scheduled',
  'published',
]

export const PLATFORMS = ['youtube', 'instagram', 'tiktok', 'shorts', 'x', 'linkedin'] as const
export const CONTENT_TYPES = ['review', 'short', 'post', 'story'] as const
export const TASK_TYPES: ContentTaskType[] = [
  'script',
  'record',
  'edit',
  'thumbnail',
  'upload',
  'seo',
  'crosspost',
  'design',
  'publish',
]
export const TASK_PRIORITIES: ContentTaskPriority[] = ['low', 'medium', 'high', 'critical']
export const CHECKLIST_PHASES: ChecklistPhase[] = [
  'pre_production',
  'production',
  'post_production',
  'upload',
]
