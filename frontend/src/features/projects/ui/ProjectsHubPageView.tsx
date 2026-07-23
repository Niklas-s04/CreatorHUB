import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../api'
import { useAuthz } from '../../../shared/hooks/useAuthz'
import { useI18n } from '../../../shared/i18n/i18n'
import { getErrorMessage } from '../../../shared/lib/errors'
import { useToast } from '../../../shared/ui/toast/ToastProvider'
import { fetchAllPages } from '../paging'
import {
  buildProjectUpdatePayload,
  isProjectDirty,
  mergeProjectKeepingDirtyFields,
  normalizeCategoryPatch,
} from '../projectForm'
import {
  PREVIEW_STATUSES,
  PROJECT_PRIORITIES,
  PROJECT_STATUSES,
  type ContentOption,
  type Page,
  type PreviewStatus,
  type ProductOption,
  type Project,
  type ProjectCategory,
  type ProjectPriority,
  type ProjectStatus,
} from '../model'

type Copy = {
  title: string
  subtitle: string
  newProject: string
  search: string
  allStatuses: string
  allCategories: string
  attention: string
  overview: string
  brief: string
  relations: string
  categories: string
  save: string
  delete: string
  noProjects: string
}

const copy: Record<'de' | 'en', Copy> = {
  de: {
    title: 'Projekte',
    subtitle: 'Briefing, Produkte, Content und Freigaben an einem Ort.',
    newProject: 'Projekt anlegen',
    search: 'Projekte durchsuchen …',
    allStatuses: 'Alle Status',
    allCategories: 'Alle Kategorien',
    attention: 'Nur Handlungsbedarf',
    overview: 'Übersicht',
    brief: 'Briefing',
    relations: 'Content & Produkte',
    categories: 'Kategorien',
    save: 'Änderungen speichern',
    delete: 'Projekt löschen',
    noProjects: 'Noch keine Projekte vorhanden.',
  },
  en: {
    title: 'Projects',
    subtitle: 'Briefs, products, content, and approvals in one place.',
    newProject: 'Create project',
    search: 'Search projects …',
    allStatuses: 'All statuses',
    allCategories: 'All categories',
    attention: 'Needs attention only',
    overview: 'Overview',
    brief: 'Brief',
    relations: 'Content & products',
    categories: 'Categories',
    save: 'Save changes',
    delete: 'Delete project',
    noProjects: 'No projects yet.',
  },
}

const statusLabels: Record<'de' | 'en', Record<ProjectStatus, string>> = {
  de: {
    idea: 'Idee',
    planning: 'Planung',
    active: 'Aktiv',
    on_hold: 'Pausiert',
    completed: 'Abgeschlossen',
    archived: 'Archiviert',
  },
  en: {
    idea: 'Idea',
    planning: 'Planning',
    active: 'Active',
    on_hold: 'On hold',
    completed: 'Completed',
    archived: 'Archived',
  },
}

const previewLabels: Record<'de' | 'en', Record<PreviewStatus, string>> = {
  de: {
    not_required: 'Nicht nötig',
    pending: 'Ausstehend',
    requested: 'Angefragt',
    changes_requested: 'Änderungen nötig',
    approved: 'Freigegeben',
  },
  en: {
    not_required: 'Not required',
    pending: 'Pending',
    requested: 'Requested',
    changes_requested: 'Changes requested',
    approved: 'Approved',
  },
}

function nullable(value: string): string | null {
  const trimmed = value.trim()
  return trimmed || null
}

function CategoryRow({
  category,
  disabled,
  onSave,
  onDelete,
}: {
  category: ProjectCategory
  disabled: boolean
  onSave: (patch: Partial<ProjectCategory>) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const [name, setName] = useState(category.name)
  const [color, setColor] = useState(category.color)
  const [description, setDescription] = useState(category.description ?? '')

  useEffect(() => {
    setName(category.name)
    setColor(category.color)
    setDescription(category.description ?? '')
  }, [category])

  return (
    <div className="project-category-row">
      <input
        className="project-color-input"
        type="color"
        value={color}
        disabled={disabled}
        aria-label="Kategoriefarbe"
        onChange={(event) => setColor(event.target.value)}
      />
      <input value={name} disabled={disabled} onChange={(event) => setName(event.target.value)} />
      <input
        value={description}
        disabled={disabled}
        placeholder="Beschreibung"
        onChange={(event) => setDescription(event.target.value)}
      />
      <label className="filter-check">
        <input
          type="checkbox"
          checked={category.is_active}
          disabled={disabled}
          onChange={() => onSave({ is_active: !category.is_active })}
        />
        Aktiv
      </label>
      <button
        className="btn"
        disabled={disabled || !name.trim()}
        onClick={() => onSave({ name: name.trim(), color, description: nullable(description) })}
      >
        Speichern
      </button>
      <button className="btn danger" disabled={disabled} onClick={onDelete}>
        Löschen
      </button>
    </div>
  )
}

export default function ProjectsHubPageView() {
  const { language } = useI18n()
  const text = copy[language]
  const toast = useToast()
  const { hasPermission, loading: authzLoading } = useAuthz()
  const canManage = hasPermission('project.manage')
  const canDelete = hasPermission('project.delete')
  const canReadContent = hasPermission('content.read') || hasPermission('content.manage')
  const canManageContent = hasPermission('content.manage')
  const canReadProducts = hasPermission('product.read') || hasPermission('product.write')
  const canWriteProducts = hasPermission('product.write')
  const [projects, setProjects] = useState<Project[]>([])
  const [categories, setCategories] = useState<ProjectCategory[]>([])
  const [contentOptions, setContentOptions] = useState<ContentOption[]>([])
  const [productOptions, setProductOptions] = useState<ProductOption[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [form, setForm] = useState<Project | null>(null)
  const [formBaseline, setFormBaseline] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'overview' | 'brief' | 'relations' | 'categories'>(
    'overview'
  )
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [attentionOnly, setAttentionOnly] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newCategoryId, setNewCategoryId] = useState('')
  const [linkContentId, setLinkContentId] = useState('')
  const [linkProductId, setLinkProductId] = useState('')
  const [inlineContentTitle, setInlineContentTitle] = useState('')
  const [inlineContentPlatform, setInlineContentPlatform] = useState('youtube')
  const [inlineContentType, setInlineContentType] = useState('review')
  const [inlineProductTitle, setInlineProductTitle] = useState('')
  const [inlineProductBrand, setInlineProductBrand] = useState('')
  const [inlineProductModel, setInlineProductModel] = useState('')
  const [newCategoryName, setNewCategoryName] = useState('')
  const [newCategoryColor, setNewCategoryColor] = useState('#5aa0ff')
  const formDirty = useMemo(() => isProjectDirty(form, formBaseline), [form, formBaseline])
  const selectedIdRef = useRef(selectedId)
  const formRef = useRef(form)
  const formBaselineRef = useRef(formBaseline)
  const formDirtyRef = useRef(formDirty)
  selectedIdRef.current = selectedId
  formRef.current = form
  formBaselineRef.current = formBaseline
  formDirtyRef.current = formDirty

  const syncProject = useCallback((project: Project, preserveDirty = false) => {
    const currentForm = formRef.current
    const currentBaseline = formBaselineRef.current
    const nextForm =
      preserveDirty && currentForm && currentBaseline
        ? mergeProjectKeepingDirtyFields(project, currentForm, currentBaseline)
        : project

    formRef.current = nextForm
    formBaselineRef.current = project
    setForm(nextForm)
    setFormBaseline(project)
    setProjects((current) => {
      const exists = current.some((item) => item.id === project.id)
      if (!exists) return [project, ...current]
      return current.map((item) => (item.id === project.id ? project : item))
    })
  }, [])

  const loadCollections = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const contentRequest = canReadContent
        ? fetchAllPages<ContentOption>(
            (path) => apiFetch<Page<ContentOption>>(path),
            '/content/items?sort_by=updated_at&sort_order=desc'
          )
            .then((items) => ({ items, error: null as unknown }))
            .catch((relationError: unknown) => ({
              items: [] as ContentOption[],
              error: relationError,
            }))
        : Promise.resolve({ items: [] as ContentOption[], error: null as unknown })
      const productRequest = canReadProducts
        ? fetchAllPages<ProductOption>(
            (path) => apiFetch<Page<ProductOption>>(path),
            '/products?sort_by=updated_at&sort_order=desc'
          )
            .then((items) => ({ items, error: null as unknown }))
            .catch((relationError: unknown) => ({
              items: [] as ProductOption[],
              error: relationError,
            }))
        : Promise.resolve({ items: [] as ProductOption[], error: null as unknown })

      const [projectItems, categoryItems, contentResult, productResult] = await Promise.all([
        fetchAllPages<Project>(
          (path) => apiFetch<Page<Project>>(path),
          '/projects?sort_by=updated_at&sort_order=desc'
        ),
        apiFetch<ProjectCategory[]>('/projects/categories?include_inactive=true'),
        contentRequest,
        productRequest,
      ])
      setProjects(projectItems)
      setCategories(categoryItems)
      if (!contentResult.error) setContentOptions(contentResult.items)
      if (!productResult.error) setProductOptions(productResult.items)

      const relationErrors = [contentResult.error, productResult.error].filter(Boolean)
      if (relationErrors.length) {
        setError(relationErrors.map(getErrorMessage).join(' '))
      }

      const hashProjectId = window.location.hash.startsWith('#project-')
        ? window.location.hash.slice('#project-'.length)
        : null
      const currentId = selectedIdRef.current
      const currentStillExists = Boolean(
        currentId && projectItems.some((item) => item.id === currentId)
      )
      if (!currentStillExists) {
        const nextId =
          projectItems.find((item) => item.id === hashProjectId)?.id ?? projectItems[0]?.id ?? null
        if (
          !formDirtyRef.current ||
          window.confirm(
            language === 'de' ? 'Ungespeicherte Änderungen verwerfen?' : 'Discard unsaved changes?'
          )
        ) {
          selectedIdRef.current = nextId
          setSelectedId(nextId)
        }
      }
    } catch (loadError) {
      setError(getErrorMessage(loadError))
    } finally {
      setLoading(false)
    }
  }, [canReadContent, canReadProducts, language])

  useEffect(() => {
    if (!authzLoading) void loadCollections()
  }, [authzLoading, loadCollections])

  useEffect(() => {
    if (!selectedId) {
      formRef.current = null
      formBaselineRef.current = null
      setForm(null)
      setFormBaseline(null)
      return
    }
    let live = true
    apiFetch<Project>(`/projects/${selectedId}`)
      .then((project) => {
        if (!live) return
        const currentForm = formRef.current
        const currentBaseline = formBaselineRef.current
        const preserveDirty =
          Boolean(currentForm && currentBaseline) &&
          currentForm?.id === project.id &&
          currentBaseline?.id === project.id &&
          isProjectDirty(currentForm, currentBaseline)
        syncProject(project, preserveDirty)
      })
      .catch((loadError) => {
        if (!live) return
        setError(getErrorMessage(loadError))
        const currentFormId = formRef.current?.id ?? null
        if (currentFormId && currentFormId !== selectedId) {
          selectedIdRef.current = currentFormId
          setSelectedId(currentFormId)
        }
      })
    return () => {
      live = false
    }
  }, [selectedId, syncProject])

  const filteredProjects = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase()
    return projects.filter((project) => {
      if (
        normalized &&
        ![project.title, project.goal, project.owner_name, project.category?.name]
          .filter(Boolean)
          .some((value) => value!.toLocaleLowerCase().includes(normalized))
      )
        return false
      if (statusFilter && project.status !== statusFilter) return false
      if (categoryFilter && project.category_id !== categoryFilter) return false
      if (attentionOnly && !project.overdue && !project.preview_attention_required) return false
      return true
    })
  }, [projects, query, statusFilter, categoryFilter, attentionOnly])

  const availableContent = useMemo(() => {
    const linked = new Set(form?.content_items?.map((item) => item.id) ?? [])
    return contentOptions.filter((item) => !linked.has(item.id))
  }, [contentOptions, form?.content_items])

  const availableProducts = useMemo(() => {
    const linked = new Set(form?.products?.map((item) => item.id) ?? [])
    return productOptions.filter((item) => !linked.has(item.id))
  }, [productOptions, form?.products])

  function setField<K extends keyof Project>(field: K, value: Project[K]) {
    if (!canManage) return
    setForm((current) => {
      const next = current ? { ...current, [field]: value } : current
      formRef.current = next
      return next
    })
  }

  function setCategory(categoryId: string | null) {
    if (!canManage) return
    setForm((current) => {
      if (!current) return current
      const next = {
        ...current,
        category_id: categoryId,
        category: categories.find((category) => category.id === categoryId) ?? null,
      }
      formRef.current = next
      return next
    })
  }

  function selectProject(projectId: string) {
    if (projectId === selectedIdRef.current) return
    if (
      formDirtyRef.current &&
      !window.confirm(
        language === 'de' ? 'Ungespeicherte Änderungen verwerfen?' : 'Discard unsaved changes?'
      )
    ) {
      return
    }
    setError(null)
    selectedIdRef.current = projectId
    setSelectedId(projectId)
  }

  async function mutateProject<T>(
    action: () => Promise<T>,
    successMessage: string,
    apply?: (result: T) => void
  ) {
    setSaving(true)
    setError(null)
    try {
      const result = await action()
      apply?.(result)
      toast.success(successMessage)
      return result
    } catch (mutationError) {
      const message = getErrorMessage(mutationError)
      setError(message)
      toast.error(message)
      return null
    } finally {
      setSaving(false)
    }
  }

  async function createProject() {
    if (!canManage || !newTitle.trim()) return
    const project = await mutateProject(
      () =>
        apiFetch<Project>('/projects', {
          method: 'POST',
          body: JSON.stringify({
            title: newTitle.trim(),
            category_id: newCategoryId || null,
            status: 'idea',
          }),
        }),
      language === 'de' ? 'Projekt wurde angelegt.' : 'Project created.'
    )
    if (!project) return
    syncProject(project)
    setSelectedId(project.id)
    setNewTitle('')
  }

  async function saveProject() {
    if (!form || !canManage || !formDirty || !form.title.trim()) return
    const payload = buildProjectUpdatePayload(form, formBaseline)
    await mutateProject(
      () =>
        apiFetch<Project>(`/projects/${form.id}`, {
          method: 'PATCH',
          body: JSON.stringify(payload),
        }),
      language === 'de' ? 'Projekt gespeichert.' : 'Project saved.',
      syncProject
    )
  }

  async function deleteProject() {
    if (!form || !canDelete || !window.confirm(`${text.delete}: ${form.title}?`)) return
    const id = form.id
    const result = await mutateProject(
      () => apiFetch<{ deleted: boolean }>(`/projects/${id}`, { method: 'DELETE' }),
      language === 'de' ? 'Projekt gelöscht.' : 'Project deleted.'
    )
    if (!result) return
    const remaining = projects.filter((item) => item.id !== id)
    setProjects(remaining)
    setSelectedId(remaining[0]?.id ?? null)
    setForm(null)
    setFormBaseline(null)
  }

  async function relationAction(path: string, method: 'POST' | 'DELETE' = 'POST', body?: object) {
    if (!form || !canManage) return null
    return mutateProject(
      () =>
        apiFetch<Project>(`/projects/${form.id}${path}`, {
          method,
          body: body ? JSON.stringify(body) : undefined,
        }),
      language === 'de' ? 'Verknüpfungen aktualisiert.' : 'Links updated.',
      (project) => syncProject(project, true)
    )
  }

  async function linkExistingContent() {
    if (!canManage || !canReadContent || !linkContentId) return
    const result = await relationAction(`/content/${linkContentId}`)
    if (result) setLinkContentId('')
  }

  async function linkExistingProduct() {
    if (!canManage || !canReadProducts || !linkProductId) return
    const result = await relationAction(`/products/${linkProductId}`)
    if (result) setLinkProductId('')
  }

  async function createContent() {
    if (!canManage || !canManageContent || !inlineContentTitle.trim()) return
    const result = await relationAction('/content', 'POST', {
      title: inlineContentTitle.trim(),
      platform: inlineContentPlatform,
      type: inlineContentType,
      status: 'idea',
    })
    if (result) {
      setInlineContentTitle('')
      await loadCollections()
      setSelectedId(result.id)
    }
  }

  async function createProduct() {
    if (!canManage || !canWriteProducts || !inlineProductTitle.trim()) return
    const result = await relationAction('/products', 'POST', {
      title: inlineProductTitle.trim(),
      brand: nullable(inlineProductBrand),
      model: nullable(inlineProductModel),
    })
    if (result) {
      setInlineProductTitle('')
      setInlineProductBrand('')
      setInlineProductModel('')
      await loadCollections()
      setSelectedId(result.id)
    }
  }

  async function createCategory() {
    if (!canManage) return
    const patch = normalizeCategoryPatch({
      name: newCategoryName,
      color: newCategoryColor,
    })
    if (!patch) {
      const message =
        language === 'de' ? 'Kategoriename darf nicht leer sein.' : 'Category name cannot be empty.'
      setError(message)
      toast.error(message)
      return
    }
    const result = await mutateProject(
      () =>
        apiFetch<ProjectCategory>('/projects/categories', {
          method: 'POST',
          body: JSON.stringify(patch),
        }),
      language === 'de' ? 'Kategorie angelegt.' : 'Category created.'
    )
    if (!result) return
    setCategories((current) => [...current, result].sort((a, b) => a.name.localeCompare(b.name)))
    setNewCategoryName('')
  }

  async function updateCategory(category: ProjectCategory, patch: Partial<ProjectCategory>) {
    if (!canManage) return
    const normalizedPatch = normalizeCategoryPatch(patch)
    if (!normalizedPatch) {
      const message =
        language === 'de' ? 'Kategoriename darf nicht leer sein.' : 'Category name cannot be empty.'
      setError(message)
      toast.error(message)
      return
    }
    const updated = await mutateProject(
      () =>
        apiFetch<ProjectCategory>(`/projects/categories/${category.id}`, {
          method: 'PATCH',
          body: JSON.stringify(normalizedPatch),
        }),
      language === 'de' ? 'Kategorie gespeichert.' : 'Category saved.'
    )
    if (!updated) return
    setCategories((current) => current.map((item) => (item.id === updated.id ? updated : item)))
    setProjects((current) =>
      current.map((project) =>
        project.category_id === updated.id ? { ...project, category: updated } : project
      )
    )
    setForm((current) => {
      const next = current?.category_id === updated.id ? { ...current, category: updated } : current
      formRef.current = next
      return next
    })
    setFormBaseline((current) => {
      const next = current?.category_id === updated.id ? { ...current, category: updated } : current
      formBaselineRef.current = next
      return next
    })
  }

  async function deleteCategory(category: ProjectCategory) {
    if (!canManage) return
    if (!window.confirm(`${category.name} löschen? Projekte behalten ihre Daten.`)) return
    const result = await mutateProject(
      () =>
        apiFetch<{ deleted: boolean }>(`/projects/categories/${category.id}`, {
          method: 'DELETE',
        }),
      language === 'de' ? 'Kategorie gelöscht.' : 'Category deleted.'
    )
    if (!result) return
    setCategories((current) => current.filter((item) => item.id !== category.id))
    setNewCategoryId((current) => (current === category.id ? '' : current))
    setCategoryFilter((current) => (current === category.id ? '' : current))
    setForm((current) => {
      const next =
        current?.category_id === category.id
          ? { ...current, category_id: null, category: null }
          : current
      formRef.current = next
      return next
    })
    setFormBaseline((current) => {
      const next =
        current?.category_id === category.id
          ? { ...current, category_id: null, category: null }
          : current
      formBaselineRef.current = next
      return next
    })
    await loadCollections()
  }

  return (
    <div className="container projects-page">
      <div className="page-header">
        <div>
          <h2 className="page-title">{text.title}</h2>
          <div className="page-subtitle">{text.subtitle}</div>
        </div>
        {canManage && (
          <div className="project-create-bar">
            <input
              value={newTitle}
              placeholder={language === 'de' ? 'Projektname …' : 'Project name …'}
              onChange={(event) => setNewTitle(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void createProject()
              }}
            />
            <select
              value={newCategoryId}
              onChange={(event) => setNewCategoryId(event.target.value)}
            >
              <option value="">{language === 'de' ? 'Ohne Kategorie' : 'No category'}</option>
              {categories
                .filter((category) => category.is_active)
                .map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
            </select>
            <button
              className="btn primary"
              disabled={!newTitle.trim() || saving}
              onClick={createProject}
            >
              + {text.newProject}
            </button>
          </div>
        )}
      </div>

      {error && <div className="inline-hint error">{error}</div>}

      <div className="project-filters card tight">
        <input
          value={query}
          placeholder={text.search}
          onChange={(event) => setQuery(event.target.value)}
        />
        <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
          <option value="">{text.allStatuses}</option>
          {PROJECT_STATUSES.map((status) => (
            <option key={status} value={status}>
              {statusLabels[language][status]}
            </option>
          ))}
        </select>
        <select value={categoryFilter} onChange={(event) => setCategoryFilter(event.target.value)}>
          <option value="">{text.allCategories}</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
        <label className="filter-check">
          <input
            type="checkbox"
            checked={attentionOnly}
            onChange={(event) => setAttentionOnly(event.target.checked)}
          />
          {text.attention}
        </label>
        <button className="btn" onClick={() => void loadCollections()}>
          ↻
        </button>
      </div>

      <div className="projects-workspace">
        <aside className="project-list card" aria-label={text.title}>
          {loading && <div className="muted">{language === 'de' ? 'Lädt …' : 'Loading …'}</div>}
          {!loading && filteredProjects.length === 0 && (
            <div className="muted">{text.noProjects}</div>
          )}
          {filteredProjects.map((project) => (
            <button
              type="button"
              key={project.id}
              className={
                selectedId === project.id ? 'project-list-item active' : 'project-list-item'
              }
              onClick={() => selectProject(project.id)}
            >
              <div className="row between">
                <span className="title-strong">{project.title}</span>
                <span className={`project-priority ${project.priority}`}>{project.priority}</span>
              </div>
              <div className="project-card-meta">
                {project.category && (
                  <span className="project-category-pill">
                    <i style={{ backgroundColor: project.category.color }} />
                    {project.category.name}
                  </span>
                )}
                <span>{statusLabels[language][project.status]}</span>
              </div>
              <div className="project-progress" aria-label={`${project.progress_percent}%`}>
                <span style={{ width: `${project.progress_percent}%` }} />
              </div>
              <div className="row between small muted">
                <span>
                  ▤ {project.content_count} · ◇ {project.product_count}
                </span>
                <span className={project.overdue ? 'error' : ''}>{project.due_date ?? '—'}</span>
              </div>
              {(project.overdue || project.preview_attention_required) && (
                <div className="project-attention">
                  {project.overdue ? 'Termin überfällig' : 'Preview offen'}
                </div>
              )}
            </button>
          ))}
        </aside>

        <section className="project-detail">
          {!form ? (
            <div className="card muted">
              {language === 'de' ? 'Wähle ein Projekt aus.' : 'Select a project.'}
            </div>
          ) : (
            <>
              <div className="card project-detail-head">
                <div>
                  <div className="project-eyebrow">
                    {form.category?.name ?? (language === 'de' ? 'Ohne Kategorie' : 'No category')}
                  </div>
                  <h2 className="no-margin">{form.title}</h2>
                  <div className="small muted">
                    {statusLabels[language][form.status]} · {form.content_count} Content ·{' '}
                    {form.product_count} Produkte
                  </div>
                </div>
                <div className="project-detail-actions">
                  {canManage && (
                    <button
                      className="btn primary"
                      disabled={saving || !formDirty || !form.title.trim()}
                      onClick={saveProject}
                    >
                      {saving ? '…' : text.save}
                    </button>
                  )}
                  {canDelete && (
                    <button className="btn danger" disabled={saving} onClick={deleteProject}>
                      {text.delete}
                    </button>
                  )}
                </div>
              </div>

              <div className="project-tabs" role="tablist">
                {(
                  [
                    ['overview', text.overview],
                    ['brief', text.brief],
                    ['relations', text.relations],
                    ['categories', text.categories],
                  ] as const
                ).map(([key, label]) => (
                  <button
                    key={key}
                    role="tab"
                    aria-selected={activeTab === key}
                    className={activeTab === key ? 'btn primary' : 'btn'}
                    onClick={() => setActiveTab(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>

              {activeTab === 'overview' && (
                <div className="card stack">
                  <div className="form-grid">
                    <label className="form-field wide">
                      <span className="field-label">
                        {language === 'de' ? 'Projektname' : 'Project name'}
                      </span>
                      <input
                        value={form.title}
                        disabled={!canManage}
                        onChange={(event) => setField('title', event.target.value)}
                      />
                    </label>
                    <label className="form-field">
                      <span className="field-label">{text.categories}</span>
                      <select
                        value={form.category_id ?? ''}
                        disabled={!canManage}
                        onChange={(event) => setCategory(event.target.value || null)}
                      >
                        <option value="">—</option>
                        {categories
                          .filter(
                            (category) => category.is_active || category.id === form.category_id
                          )
                          .map((category) => (
                            <option key={category.id} value={category.id}>
                              {category.name}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label className="form-field">
                      <span className="field-label">Status</span>
                      <select
                        value={form.status}
                        disabled={!canManage}
                        onChange={(event) =>
                          setField('status', event.target.value as ProjectStatus)
                        }
                      >
                        {PROJECT_STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {statusLabels[language][status]}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="form-field">
                      <span className="field-label">
                        {language === 'de' ? 'Priorität' : 'Priority'}
                      </span>
                      <select
                        value={form.priority}
                        disabled={!canManage}
                        onChange={(event) =>
                          setField('priority', event.target.value as ProjectPriority)
                        }
                      >
                        {PROJECT_PRIORITIES.map((priority) => (
                          <option key={priority} value={priority}>
                            {priority}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="form-field">
                      <span className="field-label">
                        {language === 'de' ? 'Verantwortlich' : 'Owner'}
                      </span>
                      <input
                        value={form.owner_name ?? ''}
                        disabled={!canManage}
                        onChange={(event) => setField('owner_name', event.target.value)}
                      />
                    </label>
                    <label className="form-field">
                      <span className="field-label">
                        {language === 'de' ? 'Start' : 'Start date'}
                      </span>
                      <input
                        type="date"
                        value={form.start_date ?? ''}
                        disabled={!canManage}
                        onChange={(event) => setField('start_date', event.target.value || null)}
                      />
                    </label>
                    <label className="form-field">
                      <span className="field-label">
                        {language === 'de' ? 'Fällig' : 'Due date'}
                      </span>
                      <input
                        type="date"
                        value={form.due_date ?? ''}
                        disabled={!canManage}
                        onChange={(event) => setField('due_date', event.target.value || null)}
                      />
                    </label>
                    <label className="form-field">
                      <span className="field-label">
                        {language === 'de' ? 'Veröffentlichung' : 'Publish date'}
                      </span>
                      <input
                        type="date"
                        value={form.publish_date ?? ''}
                        disabled={!canManage}
                        onChange={(event) => setField('publish_date', event.target.value || null)}
                      />
                    </label>
                    <label className="form-field wide">
                      <span className="field-label">
                        {language === 'de' ? 'Fortschritt' : 'Progress'} · {form.progress_percent}%
                      </span>
                      <input
                        type="range"
                        min="0"
                        max="100"
                        step="5"
                        value={form.progress_percent}
                        disabled={!canManage}
                        onChange={(event) =>
                          setField('progress_percent', Number(event.target.value))
                        }
                      />
                    </label>
                  </div>

                  <div
                    className={
                      form.preview_attention_required ? 'preview-panel attention' : 'preview-panel'
                    }
                  >
                    <div className="row between">
                      <div>
                        <div className="title-strong">Preview / Freigabe</div>
                        <div className="small muted">
                          {language === 'de'
                            ? 'Explizit festhalten, ob und bis wann eine Vorabversion nötig ist.'
                            : 'Track whether a preview is needed and when it is due.'}
                        </div>
                      </div>
                      <label className="filter-check">
                        <input
                          type="checkbox"
                          checked={form.preview_required}
                          disabled={!canManage}
                          onChange={(event) => {
                            setField('preview_required', event.target.checked)
                            setField(
                              'preview_status',
                              event.target.checked ? 'pending' : 'not_required'
                            )
                          }}
                        />
                        {language === 'de' ? 'Preview nötig' : 'Preview required'}
                      </label>
                    </div>
                    {form.preview_required && (
                      <div className="form-grid section-gap">
                        <label className="form-field">
                          <span className="field-label">Status</span>
                          <select
                            value={form.preview_status}
                            disabled={!canManage}
                            onChange={(event) =>
                              setField('preview_status', event.target.value as PreviewStatus)
                            }
                          >
                            {PREVIEW_STATUSES.map((status) => (
                              <option key={status} value={status}>
                                {previewLabels[language][status]}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="form-field">
                          <span className="field-label">
                            {language === 'de' ? 'Preview fällig' : 'Preview due'}
                          </span>
                          <input
                            type="date"
                            value={form.preview_due_date ?? ''}
                            disabled={!canManage}
                            onChange={(event) =>
                              setField('preview_due_date', event.target.value || null)
                            }
                          />
                        </label>
                        <label className="form-field wide">
                          <span className="field-label">
                            {language === 'de' ? 'Preview-Hinweise' : 'Preview notes'}
                          </span>
                          <textarea
                            value={form.preview_notes ?? ''}
                            disabled={!canManage}
                            onChange={(event) => setField('preview_notes', event.target.value)}
                          />
                        </label>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'brief' && (
                <div className="card form-grid">
                  <label className="form-field wide">
                    <span className="field-label">
                      {language === 'de' ? 'Ziel / gewünschtes Ergebnis' : 'Goal / outcome'}
                    </span>
                    <textarea
                      value={form.goal ?? ''}
                      disabled={!canManage}
                      onChange={(event) => setField('goal', event.target.value)}
                    />
                  </label>
                  <label className="form-field wide">
                    <span className="field-label">Creative Brief</span>
                    <textarea
                      className="project-textarea-large"
                      value={form.brief_md ?? ''}
                      disabled={!canManage}
                      placeholder={
                        language === 'de'
                          ? 'Zielgruppe, Kernaussage, Konzept, Format, CTA …'
                          : 'Audience, key message, concept, format, CTA …'
                      }
                      onChange={(event) => setField('brief_md', event.target.value)}
                    />
                  </label>
                  <label className="form-field wide">
                    <span className="field-label">
                      {language === 'de'
                        ? 'Muss-Kriterien / Was ist zu beachten?'
                        : 'Requirements / mandatories'}
                    </span>
                    <textarea
                      className="project-textarea-large"
                      value={form.requirements_md ?? ''}
                      disabled={!canManage}
                      placeholder={
                        language === 'de'
                          ? 'Pflichtinhalte, Claims, Disclosure, Shots, technische Vorgaben …'
                          : 'Required content, claims, disclosures, shots, technical specs …'
                      }
                      onChange={(event) => setField('requirements_md', event.target.value)}
                    />
                  </label>
                  <label className="form-field wide">
                    <span className="field-label">
                      {language === 'de' ? 'Interne Notizen' : 'Internal notes'}
                    </span>
                    <textarea
                      value={form.notes_md ?? ''}
                      disabled={!canManage}
                      onChange={(event) => setField('notes_md', event.target.value)}
                    />
                  </label>
                </div>
              )}

              {activeTab === 'relations' && (
                <div className="project-relations-grid">
                  <div className="card stack">
                    <div className="section-head">
                      <div>
                        <h3 className="no-margin">Content / Videos</h3>
                        <span className="small muted">
                          {form.content_items?.length ?? 0} verknüpft
                        </span>
                      </div>
                    </div>
                    {(form.content_items ?? []).map((item) => (
                      <div className="project-linked-row" key={item.id}>
                        <div>
                          <div className="title-strong">{item.title ?? 'Ohne Titel'}</div>
                          <div className="small muted">
                            {item.platform} · {item.type} · {item.status} · {item.readiness_score}%
                          </div>
                        </div>
                        {canManage && (
                          <button
                            className="btn"
                            aria-label="Content-Verknüpfung entfernen"
                            onClick={() => void relationAction(`/content/${item.id}`, 'DELETE')}
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                    {canManage && (canReadContent || canManageContent) && (
                      <>
                        {canReadContent && (
                          <div className="project-relation-composer">
                            <select
                              value={linkContentId}
                              onChange={(event) => setLinkContentId(event.target.value)}
                            >
                              <option value="">Bestehenden Content wählen …</option>
                              {availableContent.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.title || item.id.slice(0, 8)} · {item.platform}
                                </option>
                              ))}
                            </select>
                            <button
                              className="btn"
                              disabled={!linkContentId}
                              onClick={linkExistingContent}
                            >
                              Verknüpfen
                            </button>
                          </div>
                        )}
                        {canManageContent && (
                          <div className="project-inline-create">
                            <div className="small title-strong">Direkt neuen Content anlegen</div>
                            <input
                              value={inlineContentTitle}
                              placeholder="Video-/Content-Titel"
                              onChange={(event) => setInlineContentTitle(event.target.value)}
                            />
                            <div className="control-row">
                              <select
                                value={inlineContentPlatform}
                                onChange={(event) => setInlineContentPlatform(event.target.value)}
                              >
                                {['youtube', 'instagram', 'tiktok', 'shorts', 'x', 'linkedin'].map(
                                  (platform) => (
                                    <option key={platform} value={platform}>
                                      {platform}
                                    </option>
                                  )
                                )}
                              </select>
                              <select
                                value={inlineContentType}
                                onChange={(event) => setInlineContentType(event.target.value)}
                              >
                                {['review', 'short', 'post', 'story'].map((type) => (
                                  <option key={type} value={type}>
                                    {type}
                                  </option>
                                ))}
                              </select>
                              <button
                                className="btn primary"
                                disabled={!inlineContentTitle.trim()}
                                onClick={createContent}
                              >
                                + Anlegen
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>

                  <div className="card stack">
                    <div className="section-head">
                      <div>
                        <h3 className="no-margin">Produkte</h3>
                        <span className="small muted">{form.products?.length ?? 0} verknüpft</span>
                      </div>
                    </div>
                    {(form.products ?? []).map((item) => (
                      <div className="project-linked-row" key={item.id}>
                        <div>
                          <Link className="title-strong" to={`/products/${item.id}`}>
                            {item.title}
                          </Link>
                          <div className="small muted">
                            {[item.brand, item.model, item.category, item.status]
                              .filter(Boolean)
                              .join(' · ')}
                          </div>
                        </div>
                        {canManage && (
                          <button
                            className="btn"
                            aria-label="Produkt-Verknüpfung entfernen"
                            onClick={() => void relationAction(`/products/${item.id}`, 'DELETE')}
                          >
                            ×
                          </button>
                        )}
                      </div>
                    ))}
                    {canManage && (canReadProducts || canWriteProducts) && (
                      <>
                        {canReadProducts && (
                          <div className="project-relation-composer">
                            <select
                              value={linkProductId}
                              onChange={(event) => setLinkProductId(event.target.value)}
                            >
                              <option value="">Bestehendes Produkt wählen …</option>
                              {availableProducts.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.title} {item.brand ? `· ${item.brand}` : ''}
                                </option>
                              ))}
                            </select>
                            <button
                              className="btn"
                              disabled={!linkProductId}
                              onClick={linkExistingProduct}
                            >
                              Verknüpfen
                            </button>
                          </div>
                        )}
                        {canWriteProducts && (
                          <div className="project-inline-create">
                            <div className="small title-strong">Direkt neues Produkt anlegen</div>
                            <input
                              value={inlineProductTitle}
                              placeholder="Produktname"
                              onChange={(event) => setInlineProductTitle(event.target.value)}
                            />
                            <div className="control-row">
                              <input
                                value={inlineProductBrand}
                                placeholder="Brand"
                                onChange={(event) => setInlineProductBrand(event.target.value)}
                              />
                              <input
                                value={inlineProductModel}
                                placeholder="Modell"
                                onChange={(event) => setInlineProductModel(event.target.value)}
                              />
                              <button
                                className="btn primary"
                                disabled={!inlineProductTitle.trim()}
                                onClick={createProduct}
                              >
                                + Anlegen
                              </button>
                            </div>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </div>
              )}

              {activeTab === 'categories' && (
                <div className="card stack">
                  <div>
                    <h3 className="no-margin">{text.categories}</h3>
                    <div className="small muted">
                      {language === 'de'
                        ? 'Eigene Projekttypen mit Farbe und Beschreibung verwalten.'
                        : 'Manage custom project types with a color and description.'}
                    </div>
                  </div>
                  {canManage && (
                    <div className="project-category-create">
                      <input
                        type="color"
                        value={newCategoryColor}
                        aria-label="Neue Kategoriefarbe"
                        onChange={(event) => setNewCategoryColor(event.target.value)}
                      />
                      <input
                        value={newCategoryName}
                        placeholder={language === 'de' ? 'Neue Kategorie …' : 'New category …'}
                        onChange={(event) => setNewCategoryName(event.target.value)}
                      />
                      <button
                        className="btn primary"
                        disabled={!newCategoryName.trim()}
                        onClick={createCategory}
                      >
                        + {language === 'de' ? 'Kategorie' : 'Category'}
                      </button>
                    </div>
                  )}
                  {categories.map((category) => (
                    <CategoryRow
                      key={category.id}
                      category={category}
                      disabled={!canManage}
                      onSave={(patch) => updateCategory(category, patch)}
                      onDelete={() => deleteCategory(category)}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  )
}
