import { useCallback, useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../../../../api'
import { useI18n } from '../../../../shared/i18n/i18n'
import ContentItemEditor from './ContentItemEditor'
import ContentPlanningPanel from './ContentPlanningPanel'
import ContentPlatformProfilesPanel, { type ProfileDraft } from './ContentPlatformProfilesPanel'
import ContentTasksPanel from './ContentTasksPanel'
import ContentTemplatesPanel, { type TemplateDraft } from './ContentTemplatesPanel'
import {
  CONTENT_TYPES,
  PLATFORMS,
  STATUS_COLUMNS,
  type ApiPage,
  type ChecklistTemplate,
  type ContentItem,
  type ContentTask,
  type PlanningView,
  type PlatformProfile,
} from './contentTypes'

const TAB_KEYS = ['board', 'calendar', 'checklist', 'templates', 'platforms'] as const
type TabKey = (typeof TAB_KEYS)[number]

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  return apiFetch(path, init) as Promise<T>
}

function errorMessage(error: unknown) {
  if (error instanceof Error) return error.message
  return String(error)
}

function templatePayload(draft: TemplateDraft) {
  return {
    name: draft.name.trim(),
    description: draft.description.trim() || null,
    applies_to_platform: draft.applies_to_platform || null,
    applies_to_type: draft.applies_to_type || null,
    is_shared: draft.is_shared,
    items: draft.items
      .filter((item) => item.title.trim())
      .map((item, index) => ({
        title: item.title.trim(),
        phase: item.phase,
        required: item.required,
        priority_default: item.priority_default,
        due_offset_days: item.due_offset_days,
        can_block_publish: item.can_block_publish,
        sort_order: index,
      })),
  }
}

function profilePayload(draft: ProfileDraft) {
  return {
    platform: draft.platform,
    name: draft.name.trim(),
    is_active: draft.is_active,
    schema_json: {
      required_base_fields: draft.required_base_fields,
      fields: draft.fields
        .filter((field) => field.key?.trim())
        .map((field) => ({
          key: field.key?.trim(),
          label: field.label?.trim() || field.key?.trim(),
          type: field.type || 'text',
          required: Boolean(field.required),
          options: field.options ?? [],
        })),
    },
  }
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
  const [error, setError] = useState<string | null>(null)
  const [newTitle, setNewTitle] = useState('')
  const [newPlatform, setNewPlatform] = useState('youtube')
  const [newType, setNewType] = useState('review')

  const selected = useMemo(
    () => items.find((item) => item.id === selectedId) ?? null,
    [items, selectedId]
  )

  const selectedTasks = useMemo(
    () => tasks.filter((task) => task.content_item_id === selectedId),
    [tasks, selectedId]
  )

  const loadPlanning = useCallback(async (itemId: string) => {
    const data = await api<PlanningView>(`/content/items/${itemId}/planning-view`)
    setPlanning(data)
  }, [])

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
    if (selectedId && loadedItems.find((item) => item.id === selectedId)) {
      await loadPlanning(selectedId)
    } else if (selectedId) {
      setSelectedId(null)
      setPlanning(null)
    }
  }, [loadPlanning, selectedId])

  useEffect(() => {
    loadAll().catch((loadError) => setError(errorMessage(loadError)))
  }, [loadAll])

  useEffect(() => {
    if (!selectedId) return
    loadPlanning(selectedId).catch((loadError) => setError(errorMessage(loadError)))
  }, [selectedId, loadPlanning])

  async function createItem() {
    if (!newTitle.trim()) return
    setError(null)
    try {
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
      setActiveTab('board')
    } catch (createError) {
      setError(errorMessage(createError))
    }
  }

  async function updateItem(itemId: string, patch: Partial<ContentItem>) {
    setError(null)
    try {
      const updated = await api<ContentItem>(`/content/items/${itemId}`, {
        method: 'PATCH',
        body: JSON.stringify(patch),
      })
      setItems((prev) => prev.map((item) => (item.id === itemId ? updated : item)))
      await loadPlanning(itemId)
    } catch (updateError) {
      setError(errorMessage(updateError))
      throw updateError
    }
  }

  async function deleteItem(itemId: string) {
    await api(`/content/items/${itemId}`, { method: 'DELETE' })
    setItems((prev) => prev.filter((item) => item.id !== itemId))
    setTasks((prev) => prev.filter((task) => task.content_item_id !== itemId))
    setSelectedId(null)
    setPlanning(null)
  }

  async function createTask(itemId: string, draft: Partial<ContentTask>) {
    const created = await api<ContentTask>('/content/tasks', {
      method: 'POST',
      body: JSON.stringify({ content_item_id: itemId, status: 'todo', ...draft }),
    })
    setTasks((prev) => [created, ...prev])
    await loadPlanning(itemId)
  }

  async function updateTask(taskId: string, patch: Partial<ContentTask>) {
    const updated = await api<ContentTask>(`/content/tasks/${taskId}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
    setTasks((prev) => prev.map((task) => (task.id === taskId ? updated : task)))
    if (selectedId) await loadPlanning(selectedId)
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

  async function createTemplate(draft: TemplateDraft) {
    await api('/content/checklist-templates', {
      method: 'POST',
      body: JSON.stringify(templatePayload(draft)),
    })
    setTemplates(await api<ChecklistTemplate[]>('/content/checklist-templates'))
  }

  async function updateTemplate(templateId: string, draft: TemplateDraft) {
    await api(`/content/checklist-templates/${templateId}`, {
      method: 'PATCH',
      body: JSON.stringify(templatePayload(draft)),
    })
    setTemplates(await api<ChecklistTemplate[]>('/content/checklist-templates'))
  }

  async function deleteTemplate(templateId: string) {
    await api(`/content/checklist-templates/${templateId}`, { method: 'DELETE' })
    setTemplates(await api<ChecklistTemplate[]>('/content/checklist-templates'))
  }

  async function createProfile(draft: ProfileDraft) {
    await api('/content/platform-profiles', {
      method: 'POST',
      body: JSON.stringify(profilePayload(draft)),
    })
    setProfiles(await api<PlatformProfile[]>('/content/platform-profiles'))
  }

  async function updateProfile(profileId: string, draft: ProfileDraft) {
    const payload = profilePayload(draft)
    await api(`/content/platform-profiles/${profileId}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: payload.name,
        schema_json: payload.schema_json,
        is_active: payload.is_active,
      }),
    })
    setProfiles(await api<PlatformProfile[]>('/content/platform-profiles'))
  }

  async function deleteProfile(profileId: string) {
    await api(`/content/platform-profiles/${profileId}`, { method: 'DELETE' })
    setProfiles(await api<PlatformProfile[]>('/content/platform-profiles'))
  }

  const boardColumns = useMemo(
    () =>
      STATUS_COLUMNS.map((status) => ({
        status,
        items: items.filter((item) => item.status === status),
      })),
    [items]
  )

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
              {PLATFORMS.map((platform) => (
                <option key={platform} value={platform}>
                  {platform}
                </option>
              ))}
            </select>
            <select value={newType} onChange={(event) => setNewType(event.target.value)}>
              {CONTENT_TYPES.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
          <button className="btn primary" onClick={() => createItem()}>
            {t('contentHub.addVideo')}
          </button>
          <button
            className="btn"
            onClick={() => loadAll().catch((loadError) => setError(errorMessage(loadError)))}
          >
            {t('common.refresh')}
          </button>
        </div>
      </div>

      {error && <div className="inline-hint error">{error}</div>}

      <div className="control-row" role="tablist" aria-label={t('contentHub.tabsAriaLabel')}>
        {TAB_KEYS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={activeTab === tab}
            className={activeTab === tab ? 'btn primary' : 'btn'}
            onClick={() => setActiveTab(tab)}
          >
            {t(`contentHub.tabs.${tab}`)}
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
                          {item.platform.toUpperCase()} / {item.type.toUpperCase()} /{' '}
                          {item.readiness_score}%
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="content-side stack">
            <ContentItemEditor
              item={selected}
              profiles={profiles}
              error={error}
              onSave={updateItem}
              onDelete={deleteItem}
            />
            <ContentTasksPanel
              selectedItemId={selectedId}
              tasks={selectedTasks}
              onCreate={createTask}
              onUpdate={updateTask}
            />
          </div>
        </div>
      )}

      {activeTab === 'calendar' && (
        <div className="card stack">
          {calendarItems.map((item) => (
            <button
              key={item.id}
              className="calendar-row"
              onClick={() => {
                setSelectedId(item.id)
                setActiveTab('board')
              }}
            >
              <span>{item.publish_date || item.planned_date || '-'}</span>
              <strong>{item.title || item.id.slice(0, 8)}</strong>
              <span>{item.platform}</span>
              <span>{t(`contentHub.status.${item.status}`)}</span>
            </button>
          ))}
          {calendarItems.length === 0 && (
            <div className="muted">{t('contentHub.noPlannedContent')}</div>
          )}
        </div>
      )}

      {activeTab === 'checklist' && (
        <ContentPlanningPanel
          planning={planning}
          templates={templates}
          selectedItemId={selectedId}
          onApplyTemplate={applyTemplate}
        />
      )}

      {activeTab === 'templates' && (
        <ContentTemplatesPanel
          templates={templates}
          onCreate={createTemplate}
          onUpdate={updateTemplate}
          onDelete={deleteTemplate}
        />
      )}

      {activeTab === 'platforms' && (
        <ContentPlatformProfilesPanel
          profiles={profiles}
          onCreate={createProfile}
          onUpdate={updateProfile}
          onDelete={deleteProfile}
        />
      )}
    </div>
  )
}
