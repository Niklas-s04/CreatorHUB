import type { Project, ProjectCategory } from './model'

const EDITABLE_PROJECT_FIELDS = [
  'title',
  'category_id',
  'status',
  'priority',
  'owner_name',
  'goal',
  'brief_md',
  'requirements_md',
  'notes_md',
  'start_date',
  'due_date',
  'publish_date',
  'progress_percent',
  'preview_required',
  'preview_status',
  'preview_due_date',
  'preview_notes',
] as const satisfies ReadonlyArray<keyof Project>

function nullableText(value: string | null): string | null {
  const trimmed = value?.trim() ?? ''
  return trimmed || null
}

export function isProjectDirty(form: Project | null, baseline: Project | null): boolean {
  if (!form || !baseline || form.id !== baseline.id) return false
  return EDITABLE_PROJECT_FIELDS.some((field) => form[field] !== baseline[field])
}

export function mergeProjectKeepingDirtyFields(
  serverProject: Project,
  form: Project,
  baseline: Project
): Project {
  if (serverProject.id !== form.id || form.id !== baseline.id) return serverProject

  const dirtyValues: Record<string, unknown> = {}
  for (const field of EDITABLE_PROJECT_FIELDS) {
    if (form[field] !== baseline[field]) dirtyValues[field] = form[field]
  }

  const categoryChanged = form.category_id !== baseline.category_id
  return {
    ...serverProject,
    ...dirtyValues,
    category: categoryChanged ? form.category : serverProject.category,
  } as Project
}

function normalizedProjectPayload(form: Project) {
  return {
    title: form.title.trim(),
    category_id: form.category_id || null,
    status: form.status,
    priority: form.priority,
    owner_name: nullableText(form.owner_name),
    goal: nullableText(form.goal),
    brief_md: nullableText(form.brief_md),
    requirements_md: nullableText(form.requirements_md),
    notes_md: nullableText(form.notes_md),
    start_date: form.start_date || null,
    due_date: form.due_date || null,
    publish_date: form.publish_date || null,
    progress_percent: form.progress_percent,
    preview_required: form.preview_required,
    preview_status: form.preview_required ? form.preview_status : 'not_required',
    preview_due_date: form.preview_required ? form.preview_due_date || null : null,
    preview_notes: form.preview_required ? nullableText(form.preview_notes) : null,
  }
}

export function buildProjectUpdatePayload(
  form: Project,
  baseline: Project | null
): Partial<ReturnType<typeof normalizedProjectPayload>> {
  const normalized = normalizedProjectPayload(form)
  if (!baseline || baseline.id !== form.id) return normalized

  const normalizedBaseline = normalizedProjectPayload(baseline)
  return Object.fromEntries(
    Object.entries(normalized).filter(
      ([field, value]) => value !== normalizedBaseline[field as keyof typeof normalizedBaseline]
    )
  )
}

export function normalizeCategoryPatch(
  patch: Partial<ProjectCategory>
): Partial<ProjectCategory> | null {
  const normalized = { ...patch }
  if (typeof patch.name === 'string') {
    const name = patch.name.trim()
    if (!name) return null
    normalized.name = name
  }
  if (typeof patch.description === 'string') {
    normalized.description = nullableText(patch.description)
  }
  return normalized
}
