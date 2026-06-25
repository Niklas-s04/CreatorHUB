import { useEffect, useState } from 'react'
import { useI18n } from '../../../../shared/i18n/i18n'
import {
  CHECKLIST_PHASES,
  CONTENT_TYPES,
  PLATFORMS,
  TASK_PRIORITIES,
  type ChecklistTemplate,
  type ChecklistTemplateItem,
  type ChecklistPhase,
  type ContentTaskPriority,
} from './contentTypes'

type TemplateDraft = {
  id?: string
  name: string
  description: string
  applies_to_platform: string
  applies_to_type: string
  is_shared: boolean
  items: ChecklistTemplateItem[]
}

type Props = {
  templates: ChecklistTemplate[]
  onCreate: (draft: TemplateDraft) => Promise<void>
  onUpdate: (templateId: string, draft: TemplateDraft) => Promise<void>
  onDelete: (templateId: string) => Promise<void>
}

const EMPTY_STEP: ChecklistTemplateItem = {
  title: '',
  phase: 'production',
  required: true,
  priority_default: 'medium',
  due_offset_days: 0,
  can_block_publish: true,
  sort_order: 0,
}

const EMPTY_TEMPLATE: TemplateDraft = {
  name: '',
  description: '',
  applies_to_platform: '',
  applies_to_type: '',
  is_shared: true,
  items: [{ ...EMPTY_STEP }],
}

function toDraft(template: ChecklistTemplate): TemplateDraft {
  return {
    id: template.id,
    name: template.name,
    description: template.description ?? '',
    applies_to_platform: template.applies_to_platform ?? '',
    applies_to_type: template.applies_to_type ?? '',
    is_shared: template.is_shared,
    items:
      template.items.length > 0 ? template.items.map((item) => ({ ...item })) : [{ ...EMPTY_STEP }],
  }
}

export default function ContentTemplatesPanel({ templates, onCreate, onUpdate, onDelete }: Props) {
  const { t } = useI18n()
  const [draft, setDraft] = useState<TemplateDraft>(EMPTY_TEMPLATE)
  const [selectedId, setSelectedId] = useState<string>('')

  useEffect(() => {
    if (!selectedId) return
    const template = templates.find((item) => item.id === selectedId)
    if (template) setDraft(toDraft(template))
  }, [selectedId, templates])

  async function saveTemplate() {
    if (!draft.name.trim()) return
    if (draft.id) await onUpdate(draft.id, draft)
    else await onCreate(draft)
    setDraft(EMPTY_TEMPLATE)
    setSelectedId('')
  }

  function updateStep(index: number, patch: Partial<ChecklistTemplateItem>) {
    setDraft((current) => ({
      ...current,
      items: current.items.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item
      ),
    }))
  }

  function addStep() {
    setDraft((current) => ({
      ...current,
      items: [...current.items, { ...EMPTY_STEP, sort_order: current.items.length }],
    }))
  }

  function removeStep(index: number) {
    setDraft((current) => ({
      ...current,
      items: current.items
        .filter((_, itemIndex) => itemIndex !== index)
        .map((item, itemIndex) => ({ ...item, sort_order: itemIndex })),
    }))
  }

  return (
    <div className="content-shell">
      <div className="content-main stack">
        <div className="card">
          <div className="section-head">
            <div className="title-strong">
              {draft.id ? t('contentHub.editTemplate') : t('contentHub.createTemplate')}
            </div>
            <button
              className="btn"
              onClick={() => {
                setDraft(EMPTY_TEMPLATE)
                setSelectedId('')
              }}
            >
              {t('contentHub.newTemplate')}
            </button>
          </div>
          <div className="form-grid section-gap">
            <label className="form-field">
              <span className="field-label">{t('contentHub.templateFields.name')}</span>
              <input
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              />
            </label>
            <label className="form-field">
              <span className="field-label">{t('contentHub.templateFields.platform')}</span>
              <select
                value={draft.applies_to_platform}
                onChange={(event) =>
                  setDraft({ ...draft, applies_to_platform: event.target.value })
                }
              >
                <option value="">{t('contentHub.all')}</option>
                {PLATFORMS.map((platform) => (
                  <option key={platform} value={platform}>
                    {platform}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field">
              <span className="field-label">{t('contentHub.templateFields.type')}</span>
              <select
                value={draft.applies_to_type}
                onChange={(event) => setDraft({ ...draft, applies_to_type: event.target.value })}
              >
                <option value="">{t('contentHub.all')}</option>
                {CONTENT_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </label>
            <label className="form-field wide">
              <span className="field-label">{t('contentHub.templateFields.description')}</span>
              <textarea
                value={draft.description}
                onChange={(event) => setDraft({ ...draft, description: event.target.value })}
              />
            </label>
          </div>
          <div className="title-strong section-gap">{t('contentHub.templateSteps')}</div>
          <div className="stack section-gap">
            {draft.items.map((item, index) => (
              <div key={index} className="card tight stack">
                <div className="row between">
                  <strong>
                    {t('contentHub.step')} {index + 1}
                  </strong>
                  <button className="btn danger" onClick={() => removeStep(index)}>
                    {t('contentHub.remove')}
                  </button>
                </div>
                <div className="form-grid compact">
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.taskFields.title')}</span>
                    <input
                      value={item.title}
                      onChange={(event) => updateStep(index, { title: event.target.value })}
                    />
                  </label>
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.templateFields.phase')}</span>
                    <select
                      value={item.phase}
                      onChange={(event) =>
                        updateStep(index, { phase: event.target.value as ChecklistPhase })
                      }
                    >
                      {CHECKLIST_PHASES.map((phase) => (
                        <option key={phase} value={phase}>
                          {phase}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.taskFields.priority')}</span>
                    <select
                      value={item.priority_default}
                      onChange={(event) =>
                        updateStep(index, {
                          priority_default: event.target.value as ContentTaskPriority,
                        })
                      }
                    >
                      {TASK_PRIORITIES.map((priority) => (
                        <option key={priority} value={priority}>
                          {priority}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.templateFields.dueOffset')}</span>
                    <input
                      type="number"
                      value={item.due_offset_days ?? ''}
                      onChange={(event) =>
                        updateStep(index, {
                          due_offset_days:
                            event.target.value === '' ? null : Number(event.target.value),
                        })
                      }
                    />
                  </label>
                </div>
                <div className="control-row">
                  <label className="filter-check">
                    <input
                      type="checkbox"
                      checked={item.required}
                      onChange={(event) => updateStep(index, { required: event.target.checked })}
                    />
                    {t('contentHub.taskFields.required')}
                  </label>
                  <label className="filter-check">
                    <input
                      type="checkbox"
                      checked={item.can_block_publish}
                      onChange={(event) =>
                        updateStep(index, { can_block_publish: event.target.checked })
                      }
                    />
                    {t('contentHub.taskFields.blocksPublish')}
                  </label>
                </div>
              </div>
            ))}
          </div>
          <div className="control-row section-gap">
            <button className="btn" onClick={addStep}>
              {t('contentHub.addStep')}
            </button>
            <button className="btn primary" onClick={() => saveTemplate()}>
              {t('common.save')}
            </button>
          </div>
        </div>
      </div>
      <div className="content-side stack">
        {templates.map((template) => (
          <button
            key={template.id}
            className={template.id === selectedId ? 'kanban-card active' : 'kanban-card'}
            onClick={() => setSelectedId(template.id)}
          >
            <div className="row between">
              <strong>{template.name}</strong>
              <span>v{template.version}</span>
            </div>
            <div className="small muted">
              {template.applies_to_platform || t('contentHub.all')} /{' '}
              {template.applies_to_type || t('contentHub.all')} / {template.items.length}{' '}
              {t('contentHub.steps')}
            </div>
            {!template.is_system && (
              <span
                className="small danger-text"
                onClick={(event) => {
                  event.stopPropagation()
                  onDelete(template.id)
                }}
              >
                {t('contentHub.delete')}
              </span>
            )}
          </button>
        ))}
        {templates.length === 0 && <div className="card muted">{t('contentHub.noTemplates')}</div>}
      </div>
    </div>
  )
}

export type { TemplateDraft }
