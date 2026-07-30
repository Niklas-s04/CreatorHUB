import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import type { Page, Project } from '../model'
import ProjectsHubPageView from './ProjectsHubPageView'

const mocks = vi.hoisted(() => ({
  permissions: ['project.manage'] as string[],
  failSecondProject: false,
  apiFetch: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}))

vi.mock('../../../shared/hooks/useAuthz', () => ({
  useAuthz: () => ({
    loading: false,
    hasPermission: (permission: string) => mocks.permissions.includes(permission),
  }),
}))

vi.mock('../../../shared/i18n/i18n', () => ({
  useI18n: () => ({ language: 'en' }),
}))

vi.mock('../../../shared/ui/toast/ToastProvider', () => ({
  useToast: () => ({ success: mocks.toastSuccess, error: mocks.toastError }),
}))

vi.mock('../../../api', () => ({
  apiFetch: mocks.apiFetch,
}))

function project(id: string, title: string): Project {
  return {
    id,
    title,
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
  }
}

function page(items: Project[]): Page<Project> {
  return {
    items,
    meta: {
      limit: 100,
      offset: 0,
      total: items.length,
      sort_by: 'updated_at',
      sort_order: 'desc',
    },
  }
}

const firstProject = project('project-1', 'First project')
const secondProject = project('project-2', 'Second project')

beforeEach(() => {
  vi.clearAllMocks()
  mocks.permissions = ['project.manage']
  mocks.failSecondProject = false
  window.history.replaceState(null, '', '/')
  mocks.apiFetch.mockImplementation(async (path: string) => {
    if (path.startsWith('/projects?')) return page([firstProject, secondProject])
    if (path === '/projects/categories?include_inactive=true') return []
    if (path === '/projects/project-1') return { ...firstProject }
    if (path === '/projects/project-2') {
      if (mocks.failSecondProject) throw new Error('Project detail failed')
      return { ...secondProject }
    }
    throw new Error(`Unexpected path: ${path}`)
  })
})

function renderPage() {
  return render(
    <MemoryRouter>
      <ProjectsHubPageView />
    </MemoryRouter>
  )
}

describe('ProjectsHubPageView', () => {
  it('retains dirty fields when selection is canceled or the next detail request fails', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    renderPage()

    const title = await screen.findByLabelText('Project name')
    fireEvent.change(title, { target: { value: 'Unsaved local title' } })
    fireEvent.click(screen.getByRole('button', { name: /Second project/ }))

    expect(confirm).toHaveBeenCalledWith('Discard unsaved changes?')
    expect(mocks.apiFetch).not.toHaveBeenCalledWith('/projects/project-2')
    expect(screen.getByLabelText('Project name')).toHaveValue('Unsaved local title')

    confirm.mockReturnValue(true)
    mocks.failSecondProject = true
    fireEvent.click(screen.getByRole('button', { name: /Second project/ }))

    await screen.findByText('Project detail failed')
    await waitFor(() =>
      expect(screen.getByLabelText('Project name')).toHaveValue('Unsaved local title')
    )
  })

  it('does not expose content or product creation without their specific permissions', async () => {
    renderPage()
    await screen.findByLabelText('Project name')

    fireEvent.click(screen.getByRole('tab', { name: 'Content & products' }))

    expect(screen.queryByText('Direkt neuen Content anlegen')).not.toBeInTheDocument()
    expect(screen.queryByText('Direkt neues Produkt anlegen')).not.toBeInTheDocument()
    expect(screen.queryByText('Bestehenden Content wählen …')).not.toBeInTheDocument()
    expect(screen.queryByText('Bestehendes Produkt wählen …')).not.toBeInTheDocument()
  })
})
