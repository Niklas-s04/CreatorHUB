import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import ContentItemEditor from './ContentItemEditor'
import ContentPlatformProfilesPanel from './ContentPlatformProfilesPanel'
import ContentTemplatesPanel from './ContentTemplatesPanel'
import type { ContentItem, PlatformProfile } from './contentTypes'

const item: ContentItem = {
  id: 'content-1',
  title: 'Old title',
  hook: '',
  script_md: '',
  description_md: '',
  tags_csv: '',
  platform: 'youtube',
  type: 'review',
  status: 'idea',
  planned_date: null,
  publish_date: null,
  external_url: null,
  platform_meta_json: {},
  readiness_score: 20,
}

const profile: PlatformProfile = {
  id: 'profile-1',
  platform: 'youtube',
  name: 'YouTube default',
  schema_json: {
    required_base_fields: ['title', 'publish_date', 'description_md', 'tags_csv'],
    fields: [{ key: 'category', label: 'Category', type: 'text', required: true }],
  },
  is_active: true,
  is_system: true,
  version: 1,
}

describe('Content Hub components', () => {
  it('saves base metadata and dynamic platform fields from the item editor', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <ContentItemEditor
        item={item}
        profiles={[profile]}
        error={null}
        onSave={onSave}
        onDelete={vi.fn()}
      />
    )

    fireEvent.change(screen.getByLabelText(/Titel/), { target: { value: 'Launch video' } })
    fireEvent.change(screen.getByLabelText(/Release-Datum/), {
      target: { value: '2026-07-01' },
    })
    fireEvent.change(screen.getByLabelText(/Beschreibung/), {
      target: { value: 'Full description' },
    })
    fireEvent.change(screen.getByLabelText(/Tags/), { target: { value: 'review, gear' } })
    fireEvent.change(screen.getByLabelText(/Category/), { target: { value: 'Review' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        'content-1',
        expect.objectContaining({
          title: 'Launch video',
          publish_date: '2026-07-01',
          description_md: 'Full description',
          tags_csv: 'review, gear',
          platform_meta_json: { category: 'Review' },
        })
      )
    )
  })

  it('keeps a dirty item draft across refetches and failed saves', async () => {
    const onSave = vi.fn().mockRejectedValue(new Error('Save failed'))
    const view = render(
      <ContentItemEditor
        item={item}
        profiles={[profile]}
        error={null}
        onSave={onSave}
        onDelete={vi.fn()}
      />
    )

    const title = screen.getByLabelText(/Titel/)
    fireEvent.change(title, { target: { value: 'Unsaved local title' } })
    view.rerender(
      <ContentItemEditor
        item={{ ...item, title: 'Refetched server title', readiness_score: 30 }}
        profiles={[profile]}
        error={null}
        onSave={onSave}
        onDelete={vi.fn()}
      />
    )
    expect(screen.getByLabelText(/Titel/)).toHaveValue('Unsaved local title')

    fireEvent.change(screen.getByLabelText(/Status/), { target: { value: 'published' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))
    await waitFor(() => expect(onSave).toHaveBeenCalled())
    expect(screen.getByLabelText(/Titel/)).toHaveValue('Unsaved local title')
    expect(screen.getByLabelText(/Status/)).toHaveValue('idea')
  })

  it('patches only locally changed fields after a concurrent refetch', async () => {
    const onSave = vi.fn().mockResolvedValue(undefined)
    const view = render(
      <ContentItemEditor
        item={item}
        profiles={[profile]}
        error={null}
        onSave={onSave}
        onDelete={vi.fn()}
      />
    )

    fireEvent.change(screen.getByLabelText(/Titel/), { target: { value: 'Local title' } })
    view.rerender(
      <ContentItemEditor
        item={{ ...item, description_md: 'Concurrent server description' }}
        profiles={[profile]}
        error={null}
        onSave={onSave}
        onDelete={vi.fn()}
      />
    )
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledWith('content-1', { title: 'Local title' }))
  })

  it('creates a template with multiple checklist steps', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined)
    render(
      <ContentTemplatesPanel
        templates={[]}
        onCreate={onCreate}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
      />
    )

    let inputs = document.querySelectorAll('input')
    fireEvent.change(inputs[0], { target: { value: 'Launch checklist' } })
    fireEvent.change(inputs[1], { target: { value: 'Record intro' } })
    fireEvent.click(screen.getByRole('button', { name: '+ Schritt' }))
    inputs = document.querySelectorAll('input')
    fireEvent.change(inputs[5], { target: { value: 'Upload metadata' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Launch checklist',
          items: expect.arrayContaining([
            expect.objectContaining({ title: 'Record intro' }),
            expect.objectContaining({ title: 'Upload metadata' }),
          ]),
        })
      )
    )
  })

  it('serializes platform profile field definitions', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined)
    render(
      <ContentPlatformProfilesPanel
        profiles={[]}
        onCreate={onCreate}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
      />
    )

    fireEvent.change(screen.getByLabelText(/Name/), { target: { value: 'Creator profile' } })
    fireEvent.click(screen.getByRole('button', { name: '+ Feld' }))
    const inputs = document.querySelectorAll('input')
    fireEvent.change(inputs[10], { target: { value: 'format' } })
    fireEvent.change(inputs[11], { target: { value: 'Format' } })
    fireEvent.change(inputs[12], { target: { value: 'Reel, Story' } })
    fireEvent.click(screen.getByRole('button', { name: 'Speichern' }))

    await waitFor(() =>
      expect(onCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Creator profile',
          fields: [expect.objectContaining({ key: 'format', label: 'Format' })],
        })
      )
    )
  })
})
