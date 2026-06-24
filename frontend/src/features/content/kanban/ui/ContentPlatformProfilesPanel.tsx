import { useEffect, useState } from 'react'
import { useI18n } from '../../../../shared/i18n/i18n'
import { PLATFORMS, type PlatformField, type PlatformProfile } from './contentTypes'

type ProfileDraft = {
  id?: string
  platform: string
  name: string
  is_active: boolean
  required_base_fields: string[]
  fields: PlatformField[]
}

type Props = {
  profiles: PlatformProfile[]
  onCreate: (draft: ProfileDraft) => Promise<void>
  onUpdate: (profileId: string, draft: ProfileDraft) => Promise<void>
  onDelete: (profileId: string) => Promise<void>
}

const BASE_FIELDS = [
  'title',
  'hook',
  'script_md',
  'description_md',
  'tags_csv',
  'planned_date',
  'publish_date',
  'external_url',
]

const FIELD_TYPES = ['text', 'textarea', 'date', 'url', 'number', 'checkbox', 'select', 'tags']

const EMPTY_PROFILE: ProfileDraft = {
  platform: 'youtube',
  name: '',
  is_active: true,
  required_base_fields: ['title', 'publish_date', 'description_md', 'tags_csv'],
  fields: [],
}

function toDraft(profile: PlatformProfile): ProfileDraft {
  return {
    id: profile.id,
    platform: profile.platform,
    name: profile.name,
    is_active: profile.is_active,
    required_base_fields: profile.schema_json.required_base_fields ?? [],
    fields: (profile.schema_json.fields ?? []).map((field) => ({ ...field })),
  }
}

export default function ContentPlatformProfilesPanel({
  profiles,
  onCreate,
  onUpdate,
  onDelete,
}: Props) {
  const { t } = useI18n()
  const [selectedId, setSelectedId] = useState('')
  const [draft, setDraft] = useState<ProfileDraft>(EMPTY_PROFILE)

  useEffect(() => {
    if (!selectedId) return
    const profile = profiles.find((item) => item.id === selectedId)
    if (profile) setDraft(toDraft(profile))
  }, [selectedId, profiles])

  async function saveProfile() {
    if (!draft.name.trim()) return
    if (draft.id) await onUpdate(draft.id, draft)
    else await onCreate(draft)
    setDraft(EMPTY_PROFILE)
    setSelectedId('')
  }

  function toggleBaseField(field: string) {
    setDraft((current) => {
      const exists = current.required_base_fields.includes(field)
      return {
        ...current,
        required_base_fields: exists
          ? current.required_base_fields.filter((item) => item !== field)
          : [...current.required_base_fields, field],
      }
    })
  }

  function updateDynamicField(index: number, patch: PlatformField) {
    setDraft((current) => ({
      ...current,
      fields: current.fields.map((field, fieldIndex) =>
        fieldIndex === index ? { ...field, ...patch } : field
      ),
    }))
  }

  return (
    <div className="content-shell">
      <div className="content-main stack">
        <div className="card stack">
          <div className="section-head">
            <div className="title-strong">
              {draft.id ? t('contentHub.editPlatformProfile') : t('contentHub.createPlatformProfile')}
            </div>
            <button
              className="btn"
              onClick={() => {
                setDraft(EMPTY_PROFILE)
                setSelectedId('')
              }}
            >
              {t('contentHub.newProfile')}
            </button>
          </div>
          <div className="form-grid">
            <label className="form-field">
              <span className="field-label">{t('contentHub.profileFields.name')}</span>
              <input
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              />
            </label>
            <label className="form-field">
              <span className="field-label">{t('contentHub.profileFields.platform')}</span>
              <select
                value={draft.platform}
                disabled={Boolean(draft.id)}
                onChange={(event) => setDraft({ ...draft, platform: event.target.value })}
              >
                {PLATFORMS.map((platform) => (
                  <option key={platform} value={platform}>
                    {platform}
                  </option>
                ))}
              </select>
            </label>
            <label className="filter-check">
              <input
                type="checkbox"
                checked={draft.is_active}
                onChange={(event) => setDraft({ ...draft, is_active: event.target.checked })}
              />
              {t('contentHub.profileFields.active')}
            </label>
          </div>
          <div>
            <div className="title-strong">{t('contentHub.requiredBaseFields')}</div>
            <div className="control-row section-gap">
              {BASE_FIELDS.map((field) => (
                <label key={field} className="filter-check">
                  <input
                    type="checkbox"
                    checked={draft.required_base_fields.includes(field)}
                    onChange={() => toggleBaseField(field)}
                  />
                  {field}
                </label>
              ))}
            </div>
          </div>
          <div className="section-head">
            <div className="title-strong">{t('contentHub.dynamicFields')}</div>
            <button
              className="btn"
              onClick={() =>
                setDraft({
                  ...draft,
                  fields: [
                    ...draft.fields,
                    { key: '', label: '', type: 'text', required: false, options: [] },
                  ],
                })
              }
            >
              {t('contentHub.addField')}
            </button>
          </div>
          <div className="stack">
            {draft.fields.map((field, index) => (
              <div key={index} className="card tight">
                <div className="form-grid compact">
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.profileFields.key')}</span>
                    <input
                      value={field.key ?? ''}
                      onChange={(event) => updateDynamicField(index, { key: event.target.value })}
                    />
                  </label>
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.profileFields.label')}</span>
                    <input
                      value={field.label ?? ''}
                      onChange={(event) => updateDynamicField(index, { label: event.target.value })}
                    />
                  </label>
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.profileFields.type')}</span>
                    <select
                      value={field.type ?? 'text'}
                      onChange={(event) =>
                        updateDynamicField(index, {
                          type: event.target.value as PlatformField['type'],
                        })
                      }
                    >
                      {FIELD_TYPES.map((type) => (
                        <option key={type} value={type}>
                          {type}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="form-field">
                    <span className="field-label">{t('contentHub.profileFields.options')}</span>
                    <input
                      value={(field.options ?? []).join(', ')}
                      onChange={(event) =>
                        updateDynamicField(index, {
                          options: event.target.value
                            .split(',')
                            .map((option) => option.trim())
                            .filter(Boolean),
                        })
                      }
                    />
                  </label>
                </div>
                <div className="control-row section-gap">
                  <label className="filter-check">
                    <input
                      type="checkbox"
                      checked={Boolean(field.required)}
                      onChange={(event) =>
                        updateDynamicField(index, { required: event.target.checked })
                      }
                    />
                    {t('contentHub.profileFields.required')}
                  </label>
                  <button
                    className="btn danger"
                    onClick={() =>
                      setDraft({
                        ...draft,
                        fields: draft.fields.filter((_, fieldIndex) => fieldIndex !== index),
                      })
                    }
                  >
                    {t('contentHub.remove')}
                  </button>
                </div>
              </div>
            ))}
          </div>
          <button className="btn primary" onClick={() => saveProfile()}>
            {t('common.save')}
          </button>
        </div>
      </div>
      <div className="content-side stack">
        {profiles.map((profile) => (
          <button
            key={profile.id}
            className={profile.id === selectedId ? 'kanban-card active' : 'kanban-card'}
            onClick={() => setSelectedId(profile.id)}
          >
            <div className="row between">
              <strong>{profile.name}</strong>
              <span>v{profile.version}</span>
            </div>
            <div className="small muted">
              {profile.platform} / {profile.is_active ? t('contentHub.active') : t('contentHub.inactive')}
            </div>
            {!profile.is_system && (
              <span
                className="small danger-text"
                onClick={(event) => {
                  event.stopPropagation()
                  onDelete(profile.id)
                }}
              >
                {t('contentHub.delete')}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

export type { ProfileDraft }
