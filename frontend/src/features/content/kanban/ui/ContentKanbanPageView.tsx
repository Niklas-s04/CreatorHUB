import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../../api'
import { useI18n } from '../../../../shared/i18n/i18n'

type ApiPage<T> = { items: T[] }

type ContentItem = {
  id: string
  title: string | null
  platform: string
  type: string
  status: string
  planned_date?: string | null
  publish_date?: string | null
  platform_meta_json: Record<string, string | number | boolean | null>
  readiness_score: number
}

type ContentTask = {
  id: string
  content_item_id: string
  title: string | null
  status: 'todo' | 'doing' | 'done'
  required_for_publish: boolean
  can_block_publish: boolean
}

type PlanningView = {
  item: ContentItem
  tasks: ContentTask[]
  open_task_count: number
  required_open_count: number
  readiness_score: number
  publish_ready: boolean
  blockers: string[]
}

type PlatformProfile = {
  id: string
  platform: string
  name: string
  schema_json: {
    fields?: Array<{ key?: string; label?: string; required?: boolean }>
  }
}

type ChecklistTemplate = {
  id: string
  name: string
  applies_to_platform: string | null
  applies_to_type: string | null
  version: number
  items: Array<{
    id: string
    title: string
    phase: string
    required: boolean
    can_block_publish: boolean
  }>
}

const STATUS_COLUMNS = ['idea', 'draft', 'recorded', 'edited', 'scheduled', 'published'] as const
const TAB_KEYS = ['board', 'calendar', 'checklist', 'templates'] as const

type TabKey = (typeof TAB_KEYS)[number]

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return apiFetch(path, init) as Promise<T>
}

export default function ContentKanbanPageView() {
  const { t } = useI18n()
  const [activeTab, setActiveTab] = useState<TabKey>('board')
  const [items, setItems] = useState<ContentItem[]>([])
  const [tasks, setTasks] = useState<ContentTask[]>([])
  const [profiles, setProfiles] = useState<PlatformProfile[]>([])
  const [templates, setTemplates] = useState<ChecklistTemplate[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [planning, setPlanning] = useState<PlanningView | null>(null)

  const [newTitle, setNewTitle] = useState('')
  const [newPlatform, setNewPlatform] = useState('youtube')
  const [newType, setNewType] = useState('review')
  const [newTemplateName, setNewTemplateName] = useState('')
  const [newTemplateItemTitle, setNewTemplateItemTitle] = useState('')

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId]
  )

  const selectedTasks = useMemo(
    () => tasks.filter((task) => task.content_item_id === selectedId),
    [tasks, selectedId]
  )

  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.platform === selected?.platform),
    [profiles, selected?.platform]
  )

  const selectedPlatformFields = useMemo(() => {
    const fields = activeProfile?.schema_json?.fields
    if (!Array.isArray(fields)) return []
    return fields.filter((field) => typeof field.key === 'string' && field.key.trim() !== '')
  }, [activeProfile])

  const loadAll = useCallback(async () => {
    const [itemsPage, tasksPage, profileData, templateData] = await Promise.all([
      api<ApiPage<ContentItem>>(
        '/content/items?limit=100&offset=0&sort_by=updated_at&sort_order=desc'
      ),
      api<ApiPage<ContentTask>>(
        '/content/tasks?limit=400&offset=0&sort_by=updated_at&sort_order=desc'
      ),
      api<PlatformProfile[]>('/content/platform-profiles'),
      api<ChecklistTemplate[]>('/content/checklist-templates'),
    ])

    const loadedItems = itemsPage.items ?? []
    setItems(loadedItems)
    setTasks(tasksPage.items ?? [])
    setProfiles(profileData)
    setTemplates(templateData)

    if (selectedId && !loadedItems.find((item) => item.id === selectedId)) {
      setSelectedId(null)
      setPlanning(null)
    }
  }, [selectedId])

  const loadPlanning = useCallback(async (itemId: string) => {
    const data = await api<PlanningView>(`/content/items/${itemId}/planning-view`)
    setPlanning(data)
  }, [])

  useEffect(() => {
    loadAll().catch(console.error)
  }, [loadAll])

  useEffect(() => {
    if (!selectedId) return
    loadPlanning(selectedId).catch(console.error)
  }, [selectedId, loadPlanning])

  async function createItem() {
    if (!newTitle.trim()) return
    const created = await api<ContentItem>('/content/items', {
      method: 'POST',
      body: JSON.stringify({
        title: newTitle.trim(),
        platform: newPlatform,
        type: newType,
        status: 'idea',
        platform_meta_json: {},
      }),
    })
    setItems((prev) => [created, ...prev])
    setNewTitle('')
    setSelectedId(created.id)
  }

  async function updateItem(itemId: string, patch: Partial<ContentItem>) {
    const updated = await api<ContentItem>(`/content/items/${itemId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    setItems((prev) => prev.map((item) => (item.id === itemId ? updated : item)))
    if (selectedId === itemId) {
      await loadPlanning(itemId)
    }
  }

  async function deleteItem(itemId: string) {
    await api(`/content/items/${itemId}`, { method: 'DELETE' })
    setItems((prev) => prev.filter((item) => item.id !== itemId))
    setTasks((prev) => prev.filter((task) => task.content_item_id !== itemId))
    if (selectedId === itemId) {
      setSelectedId(null)
      setPlanning(null)
    }
  }

  async function createTask(itemId: string, title: string) {
    const created = await api<ContentTask>('/content/tasks', {
      method: 'POST',
      body: JSON.stringify({ content_item_id: itemId, title, status: 'todo' }),
    })
    setTasks((prev) => [created, ...prev])
    if (selectedId === itemId) {
      await loadPlanning(itemId)
    }
  }

  async function updateTask(taskId: string, patch: Partial<ContentTask>) {
    const updated = await api<ContentTask>(`/content/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    setTasks((prev) => prev.map((task) => (task.id === taskId ? updated : task)))
    if (selectedId) {
      await loadPlanning(selectedId)
    }
  }

  async function applyTemplate(templateId: string) {
    if (!selectedId) return
    await api(`/content/items/${selectedId}/apply-template`, {
      method: 'POST',
      body: JSON.stringify({
        template_id: templateId,
        merge_mode: 'replace',
        keep_done_tasks: false,
      }),
    })
    await loadAll()
    await loadPlanning(selectedId)
  }

  async function createTemplate() {
    if (!newTemplateName.trim() || !newTemplateItemTitle.trim()) return
    await api('/content/checklist-templates', {
      method: 'POST',
      body: JSON.stringify({
        name: newTemplateName.trim(),
        is_shared: true,
        applies_to_platform: null,
        applies_to_type: null,
        items: [
          {
            title: newTemplateItemTitle.trim(),
            phase: 'production',
            required: true,
            priority_default: 'medium',
            due_offset_days: 0,
            can_block_publish: true,
            sort_order: 0,
          },
        ],
      }),
    })
    setNewTemplateName('')
    setNewTemplateItemTitle('')
    const templateData = await api<ChecklistTemplate[]>('/content/checklist-templates')
    setTemplates(templateData)
  }

  async function updateDynamicField(fieldKey: string, value: string) {
    if (!selected) return
    const nextMeta = { ...(selected.platform_meta_json || {}), [fieldKey]: value }
    await updateItem(selected.id, { platform_meta_json: nextMeta })
  }

  const boardColumns = useMemo(() => {
    return STATUS_COLUMNS.map((status) => ({
      status,
      items: items.filter((item) => item.status === status),
    }))
  }, [items])

  const calendarItems = useMemo(
    () =>
      [...items].sort((a, b) =>
        `${a.publish_date || a.planned_date || '9999'}`.localeCompare(
          `${b.publish_date || b.planned_date || '9999'}`
        )
      ),
    [items]
  )

  return (
    <div className="container board-layout">
      <div className="page-header">
        <div>
          <h2 className="page-title">{t('contentHub.title')}</h2>
          <div className="page-subtitle">{t('contentHub.subtitle')}</div>
        </div>
        <div className="page-actions">
          <div className="control-row">
            <input
              id="content-new-title"
              className="composer-input"
              placeholder={t('contentHub.newVideoTitlePlaceholder')}
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
            />
            <select value={newPlatform} onChange={(event) => setNewPlatform(event.target.value)}>
              <option value="youtube">YouTube</option>
              <option value="instagram">Instagram</option>
              <option value="tiktok">TikTok</option>
              <option value="shorts">Shorts</option>
              <option value="x">X</option>
              <option value="linkedin">LinkedIn</option>
            </select>
            <select value={newType} onChange={(event) => setNewType(event.target.value)}>
              <option value="review">Review</option>
              <option value="short">Short</option>
              <option value="post">Post</option>
              <option value="story">Story</option>
            </select>
          </div>
          <button className="btn primary" onClick={() => createItem().catch(alert)}>
            {t('contentHub.addVideo')}
          </button>
          <button className="btn" onClick={() => loadAll().catch(alert)}>
            {t('common.refresh')}
          </button>
        </div>
      </div>

      <div className="control-row" role="tablist" aria-label={t('contentHub.tabsAriaLabel')}>
        {TAB_KEYS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            className={activeTab === tab ? 'btn primary' : 'btn'}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'board' && t('contentHub.tabs.board')}
            {tab === 'calendar' && t('contentHub.tabs.calendar')}
            {tab === 'checklist' && t('contentHub.tabs.checklist')}
            {tab === 'templates' && t('contentHub.tabs.templates')}
          </button>
        ))}
      </div>

      {activeTab === 'board' && (
        <div className="content-shell">
          <div className="content-main">
            <div className="swimlane-stack">
              {boardColumns.map((column) => (
                <div key={column.status} className="swimlane card">
                  <div className="row between swimlane-label">
                    <div>{t(`contentHub.status.${column.status}`)}</div>
                    <span className="muted small">{column.items.length}</span>
                  </div>
                  <div className="stack">
                    {column.items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className={item.id === selectedId ? 'kanban-card active' : 'kanban-card'}
                        onClick={() => setSelectedId(item.id)}
                      >
                        <div>{item.title || item.id.slice(0, 8)}</div>
                        <div className="small muted">
                          {item.platform.toUpperCase()} • {item.type.toUpperCase()} •{' '}
                          {item.readiness_score}%
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="content-side">
            {!selected ? (
              <div className="card muted">{t('contentHub.selectItem')}</div>
            ) : (
              <div className="stack">
                <div className="card">
                  <div className="section-head">
                    <h3 className="no-margin">{selected.title || t('contentHub.untitled')}</h3>
                    <button
                      className="btn danger"
                      onClick={() => deleteItem(selected.id).catch(alert)}
                    >
                      {t('contentHub.delete')}
                    </button>
                  </div>
                  <hr />
                  <div className="stack">
                    <select
                      value={selected.status}
                      onChange={(event) =>
                        updateItem(selected.id, { status: event.target.value }).catch(alert)
                      }
                    >
                      {STATUS_COLUMNS.map((status) => (
                        <option key={status} value={status}>
                          {t(`contentHub.status.${status}`)}
                        </option>
                      ))}
                    </select>
                    {selectedPlatformFields.map((field) => {
                      const key = field.key as string
                      return (
                        <div key={key}>
                          <div className="field-label">
                            {field.label || key}
                            {field.required ? ' *' : ''}
                          </div>
                          <input
                            value={String(selected.platform_meta_json?.[key] ?? '')}
                            onChange={(event) =>
                              updateDynamicField(key, event.target.value).catch(alert)
                            }
                          />
                        </div>
                      )
                    })}
                  </div>
                </div>
                <div className="card">
                  <div className="title-strong">{t('contentHub.tasksTitle')}</div>
                  <TaskComposer onAdd={(title) => createTask(selected.id, title).catch(alert)} />
                  <div className="stack section-gap">
                    {selectedTasks.map((task) => (
                      <div key={task.id} className="card tight">
                        <div>{task.title || t('contentHub.taskFallback')}</div>
                        <div className="control-row section-gap">
                          {['todo', 'doing', 'done'].map((status) => (
                            <button
                              key={status}
                              className={task.status === status ? 'btn primary' : 'btn'}
                              onClick={() =>
                                updateTask(task.id, {
                                  status: status as ContentTask['status'],
                                }).catch(alert)
                              }
                            >
                              {t(`contentHub.taskStatus.${status}`)}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'calendar' && (
        <div className="card stack">
          {calendarItems.map((item) => (
            <button key={item.id} className="btn" onClick={() => setSelectedId(item.id)}>
              {item.publish_date || item.planned_date || '-'} • {item.title || item.id.slice(0, 8)}
            </button>
          ))}
          {calendarItems.length === 0 && (
            <div className="muted">{t('contentHub.noPlannedContent')}</div>
          )}
        </div>
      )}

      {activeTab === 'checklist' && (
        <div className="card stack">
          {!selectedId || !planning ? (
            <div className="muted">{t('contentHub.selectItemForPlanning')}</div>
          ) : (
            <>
              <div>
                {t('contentHub.readiness')}: <strong>{planning.readiness_score}%</strong>
              </div>
              <div>
                {t('contentHub.publishReady')}:{' '}
                {planning.publish_ready ? t('common.yes') : t('common.no')}
              </div>
              {planning.blockers.length > 0 && (
                <div className="stack">
                  {planning.blockers.map((blocker) => (
                    <div key={blocker} className="pill">
                      {blocker}
                    </div>
                  ))}
                </div>
              )}
              {templates.length > 0 && (
                <div className="control-row">
                  {templates.slice(0, 4).map((template) => (
                    <button
                      key={template.id}
                      className="btn"
                      onClick={() => applyTemplate(template.id).catch(alert)}
                    >
                      {t('contentHub.apply')}: {template.name}
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'templates' && (
        <div className="stack">
          <div className="card">
            <div className="title-strong">{t('contentHub.createTemplate')}</div>
            <div className="control-row">
              <input
                value={newTemplateName}
                placeholder={t('contentHub.templateNamePlaceholder')}
                onChange={(event) => setNewTemplateName(event.target.value)}
              />
              <input
                value={newTemplateItemTitle}
                placeholder={t('contentHub.firstChecklistItemPlaceholder')}
                onChange={(event) => setNewTemplateItemTitle(event.target.value)}
              />
              <button className="btn primary" onClick={() => createTemplate().catch(alert)}>
                {t('common.save')}
              </button>
            </div>
          </div>
          <div className="card stack">
            {templates.map((template) => (
              <div key={template.id} className="card tight">
                <div className="row between">
                  <strong>{template.name}</strong>
                  <span className="muted">v{template.version}</span>
                </div>
                <div className="muted small">
                  {template.applies_to_platform || t('contentHub.all')} •{' '}
                  {template.applies_to_type || t('contentHub.all')}
                </div>
                <div className="small">
                  {t('contentHub.templateItemsCount', { count: template.items.length })}
                </div>
              </div>
            ))}
            {templates.length === 0 && <div className="muted">{t('contentHub.noTemplates')}</div>}
          </div>
        </div>
      )}
    </div>
  )
}

function TaskComposer({ onAdd }: { onAdd: (title: string) => void }) {
  const { t } = useI18n()
  const [title, setTitle] = useState('')
  return (
    <div className="control-row stretch">
      <input
        id="content-task-new-title"
        className="grow"
        value={title}
        onChange={(event) => setTitle(event.target.value)}
        placeholder={t('contentHub.newTaskPlaceholder')}
      />
      <button
        className="btn primary"
        onClick={() => {
          if (!title.trim()) return
          onAdd(title.trim())
          setTitle('')
        }}
      >
        {t('contentHub.add')}
      </button>
    </div>
  )
}
