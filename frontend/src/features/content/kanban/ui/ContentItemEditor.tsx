import { useEffect, useMemo, useRef, useState } from 'react'
import { useI18n } from '../../../../shared/i18n/i18n'
import {
  CONTENT_TYPES,
  PLATFORMS,
  STATUS_COLUMNS,
  type ContentItem,
  type PlatformField,
  type PlatformProfile,
} from './contentTypes'

type ItemForm = {
  title: string
  hook: string
  script_md: string
  description_md: string
  tags_csv: string
  platform: string
  type: string
  status: string
  planned_date: string
  publish_date: string
  external_url: string
  platform_meta_json: Record<string, string | number | boolean | null>
}

type Props = {
  item: ContentItem | null
  profiles: PlatformProfile[]
  error: string | null
  onSave: (itemId: string, patch: Partial<ContentItem>) => Promise<void>
  onDelete: (itemId: string) => Promise<void>
}

function toForm(item: ContentItem): ItemForm {
  return {
    title: item.title ?? '',
    hook: item.hook ?? '',
    script_md: item.script_md ?? '',
    description_md: item.description_md ?? '',
    tags_csv: item.tags_csv ?? '',
    platform: item.platform,
    type: item.type,
    status: item.status,
    planned_date: item.planned_date ?? '',
    publish_date: item.publish_date ?? '',
    external_url: item.external_url ?? '',
    platform_meta_json: { ...(item.platform_meta_json ?? {}) },
  }
}

function emptyToNull(value: string) {
  return value.trim() === '' ? null : value.trim()
}

function fieldValueToString(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined) return ''
  return String(value)
}

function toUpdateValues(form: ItemForm): Partial<ContentItem> {
  return {
    title: emptyToNull(form.title),
    hook: emptyToNull(form.hook),
    script_md: emptyToNull(form.script_md),
    description_md: emptyToNull(form.description_md),
    tags_csv: emptyToNull(form.tags_csv),
    platform: form.platform,
    type: form.type,
    status: form.status as ContentItem['status'],
    planned_date: form.planned_date || null,
    publish_date: form.publish_date || null,
    external_url: emptyToNull(form.external_url),
    platform_meta_json: form.platform_meta_json,
  }
}

function buildDirtyPatch(form: ItemForm, baseline: ItemForm): Partial<ContentItem> {
  const current = toUpdateValues(form)
  const original = toUpdateValues(baseline)
  return Object.fromEntries(
    Object.entries(current).filter(([key, value]) => {
      const originalValue = original[key as keyof ContentItem]
      return JSON.stringify(value) !== JSON.stringify(originalValue)
    })
  ) as Partial<ContentItem>
}

export default function ContentItemEditor({ item, profiles, error, onSave, onDelete }: Props) {
  const { t } = useI18n()
  const [form, setForm] = useState<ItemForm | null>(() => (item ? toForm(item) : null))
  const [baseline, setBaseline] = useState<ItemForm | null>(() => (item ? toForm(item) : null))
  const itemIdRef = useRef(item?.id ?? null)
  const [saving, setSaving] = useState(false)
  const formDirty = useMemo(
    () => Boolean(form && baseline && JSON.stringify(form) !== JSON.stringify(baseline)),
    [baseline, form]
  )

  useEffect(() => {
    if (!item) {
      itemIdRef.current = null
      setForm(null)
      setBaseline(null)
      return
    }

    const next = toForm(item)
    const itemChanged = itemIdRef.current !== item.id
    if (itemChanged || !formDirty) {
      itemIdRef.current = item.id
      setForm(next)
      setBaseline(next)
    }
  }, [formDirty, item])

  const activeProfile = useMemo(
    () => profiles.find((profile) => profile.platform === form?.platform && profile.is_active),
    [form?.platform, profiles]
  )

  const platformFields = useMemo(() => {
    const fields = activeProfile?.schema_json?.fields
    if (!Array.isArray(fields)) return []
    return fields.filter((field) => typeof field.key === 'string' && field.key.trim() !== '')
  }, [activeProfile])

  const requiredBaseFields = useMemo(() => {
    const fields = activeProfile?.schema_json?.required_base_fields
    return Array.isArray(fields) ? fields.filter((field) => typeof field === 'string') : []
  }, [activeProfile])

  if (!item || !form) {
    return <div className="card muted">{t('contentHub.selectItem')}</div>
  }
  const currentItem = item
  const currentForm = form

  function setField<K extends keyof ItemForm>(key: K, value: ItemForm[K]) {
    setForm((current) => (current ? { ...current, [key]: value } : current))
  }

  function setMeta(field: PlatformField, value: string | boolean) {
    const key = field.key?.trim()
    if (!key) return
    setForm((current) => {
      if (!current) return current
      return {
        ...current,
        platform_meta_json: {
          ...current.platform_meta_json,
          [key]: value,
        },
      }
    })
  }

  async function save() {
    setSaving(true)
    try {
      const patch = baseline ? buildDirtyPatch(currentForm, baseline) : toUpdateValues(currentForm)
      if (Object.keys(patch).length > 0) {
        await onSave(currentItem.id, patch)
      }
      setBaseline(currentForm)
    } catch {
      // Retain editable content for a retry, but never leave a rejected workflow state
      // selected because that suggests the transition succeeded.
      if (currentForm.status !== currentItem.status) {
        setForm((current) => (current ? { ...current, status: currentItem.status } : current))
      }
    } finally {
      setSaving(false)
    }
  }

  function renderDynamicField(field: PlatformField) {
    const key = field.key?.trim()
    if (!key) return null
    const type = field.type || 'text'
    const value = currentForm.platform_meta_json?.[key]
    const label = field.label || key
    return (
      <label key={key} className="form-field">
        <span className="field-label">
          {label}
          {field.required ? ' *' : ''}
        </span>
        {type === 'textarea' ? (
          <textarea
            value={fieldValueToString(value)}
            placeholder={field.placeholder}
            onChange={(event) => setMeta(field, event.target.value)}
          />
        ) : type === 'checkbox' ? (
          <input
            type="checkbox"
            checked={Boolean(value)}
            onChange={(event) => setMeta(field, event.target.checked)}
          />
        ) : type === 'select' ? (
          <select
            value={fieldValueToString(value)}
            onChange={(event) => setMeta(field, event.target.value)}
          >
            <option value="">{t('contentHub.selectOption')}</option>
            {(field.options ?? []).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        ) : (
          <input
            type={type === 'tags' ? 'text' : type}
            value={fieldValueToString(value)}
            placeholder={field.placeholder}
            onChange={(event) => setMeta(field, event.target.value)}
          />
        )}
        {field.help_text && <span className="small muted">{field.help_text}</span>}
      </label>
    )
  }

  function requiredMarker(field: keyof ItemForm) {
    return requiredBaseFields.includes(field) ? ' *' : ''
  }

  return (
    <div className="card content-editor">
      <div className="section-head">
        <div>
          <h3 className="no-margin">{form.title || t('contentHub.untitled')}</h3>
          <div className="small muted">
            {currentForm.platform.toUpperCase()} / {currentForm.type.toUpperCase()} /{' '}
            {currentItem.readiness_score}%
          </div>
        </div>
        <button className="btn danger" onClick={() => onDelete(currentItem.id)}>
          {t('contentHub.delete')}
        </button>
      </div>
      {error && <div className="inline-hint error">{error}</div>}
      <div className="form-grid section-gap">
        <label className="form-field">
          <span className="field-label">
            {t('contentHub.fields.title')}
            {requiredMarker('title')}
          </span>
          <input value={form.title} onChange={(event) => setField('title', event.target.value)} />
        </label>
        <label className="form-field">
          <span className="field-label">
            {t('contentHub.fields.hook')}
            {requiredMarker('hook')}
          </span>
          <input value={form.hook} onChange={(event) => setField('hook', event.target.value)} />
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.fields.platform')}</span>
          <select
            value={form.platform}
            onChange={(event) => setField('platform', event.target.value)}
          >
            {PLATFORMS.map((platform) => (
              <option key={platform} value={platform}>
                {platform}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.fields.type')}</span>
          <select value={form.type} onChange={(event) => setField('type', event.target.value)}>
            {CONTENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">{t('contentHub.fields.status')}</span>
          <select value={form.status} onChange={(event) => setField('status', event.target.value)}>
            {STATUS_COLUMNS.map((status) => (
              <option key={status} value={status}>
                {t(`contentHub.status.${status}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="form-field">
          <span className="field-label">
            {t('contentHub.fields.plannedDate')}
            {requiredMarker('planned_date')}
          </span>
          <input
            type="date"
            value={form.planned_date}
            onChange={(event) => setField('planned_date', event.target.value)}
          />
        </label>
        <label className="form-field">
          <span className="field-label">
            {t('contentHub.fields.publishDate')}
            {requiredMarker('publish_date')}
          </span>
          <input
            type="date"
            value={form.publish_date}
            onChange={(event) => setField('publish_date', event.target.value)}
          />
        </label>
        <label className="form-field">
          <span className="field-label">
            {t('contentHub.fields.externalUrl')}
            {requiredMarker('external_url')}
          </span>
          <input
            type="url"
            value={form.external_url}
            onChange={(event) => setField('external_url', event.target.value)}
          />
        </label>
        <label className="form-field wide">
          <span className="field-label">
            {t('contentHub.fields.description')}
            {requiredMarker('description_md')}
          </span>
          <textarea
            value={form.description_md}
            onChange={(event) => setField('description_md', event.target.value)}
          />
        </label>
        <label className="form-field wide">
          <span className="field-label">
            {t('contentHub.fields.script')}
            {requiredMarker('script_md')}
          </span>
          <textarea
            value={form.script_md}
            onChange={(event) => setField('script_md', event.target.value)}
          />
        </label>
        <label className="form-field wide">
          <span className="field-label">
            {t('contentHub.fields.tags')}
            {requiredMarker('tags_csv')}
          </span>
          <input
            value={form.tags_csv}
            placeholder={t('contentHub.tagsPlaceholder')}
            onChange={(event) => setField('tags_csv', event.target.value)}
          />
        </label>
      </div>
      {platformFields.length > 0 && (
        <>
          <div className="title-strong section-gap">{t('contentHub.platformFields')}</div>
          <div className="form-grid section-gap">{platformFields.map(renderDynamicField)}</div>
        </>
      )}
      <div className="control-row section-gap">
        <button className="btn primary" disabled={saving} onClick={() => save()}>
          {saving ? t('contentHub.saving') : t('common.save')}
        </button>
      </div>
    </div>
  )
}
