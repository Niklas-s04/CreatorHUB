import { describe, expect, it } from 'vitest'
import type { Project } from './model'
import {
  buildProjectUpdatePayload,
  isProjectDirty,
  mergeProjectKeepingDirtyFields,
  normalizeCategoryPatch,
} from './projectForm'

function project(overrides: Partial<Project> = {}): Project {
  return {
    id: 'project-1',
    title: 'Original title',
    category_id: null,
    category: null,
    status: 'idea',
    priority: 'medium',
    owner_user_id: null,
    owner_name: null,
    goal: null,
    brief_md: null,
    requirements_md: null,
    notes_md: null,
    start_date: null,
    due_date: null,
    publish_date: null,
    progress_percent: 0,
    preview_required: false,
    preview_status: 'not_required',
    preview_due_date: null,
    preview_notes: null,
    content_count: 0,
    product_count: 0,
    overdue: false,
    preview_attention_required: false,
    content_items: [],
    products: [],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

describe('project form helpers', () => {
  it('retains local dirty fields while accepting refreshed relationship data', () => {
    const baseline = project()
    const draft = project({ title: 'Local draft' })
    const server = project({
      updated_at: '2026-01-02T00:00:00Z',
      content_count: 1,
      content_items: [
        {
          id: 'content-1',
          title: 'Video',
          platform: 'youtube',
          type: 'review',
          status: 'idea',
          planned_date: null,
          publish_date: null,
          readiness_score: 0,
        },
      ],
    })

    expect(isProjectDirty(draft, baseline)).toBe(true)
    expect(mergeProjectKeepingDirtyFields(server, draft, baseline)).toMatchObject({
      title: 'Local draft',
      content_count: 1,
      updated_at: '2026-01-02T00:00:00Z',
    })
  })

  it('rejects empty category names and trims valid names', () => {
    expect(normalizeCategoryPatch({ name: '   ' })).toBeNull()
    expect(normalizeCategoryPatch({ name: '  Reviews  ', description: '   ' })).toMatchObject({
      name: 'Reviews',
      description: null,
    })
  })

  it('patches only changed fields so concurrent server fields are not overwritten', () => {
    const baseline = project({ title: 'Original', notes_md: 'Server notes', progress_percent: 10 })
    const draft = project({
      title: 'Local title',
      notes_md: 'Server notes',
      progress_percent: 10,
    })

    expect(buildProjectUpdatePayload(draft, baseline)).toEqual({ title: 'Local title' })
  })

  it('clears dependent preview fields when preview is disabled', () => {
    const baseline = project({
      preview_required: true,
      preview_status: 'requested',
      preview_due_date: '2026-08-01',
      preview_notes: 'Awaiting client',
    })
    const draft = project({
      preview_required: false,
      preview_status: 'requested',
      preview_due_date: '2026-08-01',
      preview_notes: 'Awaiting client',
    })

    expect(buildProjectUpdatePayload(draft, baseline)).toEqual({
      preview_required: false,
      preview_status: 'not_required',
      preview_due_date: null,
      preview_notes: null,
    })
  })
})
