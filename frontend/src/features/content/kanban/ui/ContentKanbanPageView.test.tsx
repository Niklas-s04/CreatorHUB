import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import ContentKanbanPageView from './ContentKanbanPageView'

const mocks = vi.hoisted(() => ({
  canManage: false,
  apiFetch: vi.fn(),
}))

vi.mock('../../../../api', () => ({
  ACTION_CONFIRMATION_HEADERS: { 'X-Action-Confirm': 'CONFIRM' },
  apiFetch: mocks.apiFetch,
}))

vi.mock('../../../../shared/hooks/useAuthz', () => ({
  useAuthz: () => ({
    hasPermission: (permission: string) => permission === 'content.manage' && mocks.canManage,
  }),
}))

const contentItem = {
  id: 'content-1',
  title: 'Camera review',
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

beforeEach(() => {
  vi.clearAllMocks()
  mocks.canManage = false
  mocks.apiFetch.mockImplementation(async (path: string, options?: RequestInit) => {
    if (path.startsWith('/content/items?')) return { items: [contentItem] }
    if (path.startsWith('/content/tasks?')) return { items: [] }
    if (path === '/content/platform-profiles') return []
    if (path === '/content/checklist-templates') return []
    if (path === '/content/items/content-1/planning-view') {
      return {
        item: contentItem,
        tasks: [],
        open_task_count: 0,
        required_open_count: 0,
        readiness_score: 20,
        publish_ready: false,
        blockers: [],
      }
    }
    if (path === '/content/items/content-1' && options?.method === 'DELETE') {
      return { deleted: true }
    }
    throw new Error(`Unexpected path: ${path}`)
  })
})

describe('ContentKanbanPageView RBAC', () => {
  it('keeps the content workspace read-only without content.manage', async () => {
    render(<ContentKanbanPageView />)

    const card = await screen.findByRole('button', { name: /Camera review/ })
    expect(document.querySelector('#content-new-title')).toBeNull()
    expect(screen.queryByRole('tab', { name: 'Vorlagen' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Plattformfelder' })).not.toBeInTheDocument()

    fireEvent.click(card)
    await waitFor(() =>
      expect(mocks.apiFetch).toHaveBeenCalledWith(
        '/content/items/content-1/planning-view',
        undefined
      )
    )
    expect(screen.queryByRole('button', { name: 'Löschen' })).not.toBeInTheDocument()
    expect(
      mocks.apiFetch.mock.calls.filter(([, options]) => options?.method && options.method !== 'GET')
    ).toHaveLength(0)
  })

  it('shows content creation and configuration actions to managers', async () => {
    mocks.canManage = true
    render(<ContentKanbanPageView />)

    await screen.findByRole('button', { name: /Camera review/ })
    expect(document.querySelector('#content-new-title')).not.toBeNull()
    expect(screen.getByRole('tab', { name: 'Vorlagen' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Plattformfelder' })).toBeInTheDocument()
  })

  it('requires a click confirmation and sends it with content deletion', async () => {
    mocks.canManage = true
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    render(<ContentKanbanPageView />)

    fireEvent.click(await screen.findByRole('button', { name: /Camera review/ }))
    const deleteButton = await screen.findByRole('button', { name: 'Löschen' })
    fireEvent.click(deleteButton)
    expect(mocks.apiFetch).not.toHaveBeenCalledWith(
      '/content/items/content-1',
      expect.objectContaining({ method: 'DELETE' })
    )

    confirm.mockReturnValue(true)
    fireEvent.click(deleteButton)

    await waitFor(() =>
      expect(mocks.apiFetch).toHaveBeenCalledWith('/content/items/content-1', {
        method: 'DELETE',
        headers: { 'X-Action-Confirm': 'CONFIRM' },
      })
    )
    expect(confirm).toHaveBeenCalledWith(
      'Camera review löschen? Diese Aktion kann nicht rückgängig gemacht werden.'
    )
    confirm.mockRestore()
  })
})
