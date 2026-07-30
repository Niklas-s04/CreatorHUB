import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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
  ACTION_CONFIRMATION_HEADERS: { 'X-Action-Confirm': 'CONFIRM' },
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
      sort_by: 'due_date',
      sort_order: 'asc',
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

  it('deletes a project after a click confirmation without requesting MFA', async () => {
    mocks.permissions = ['project.manage', 'project.delete']
    mocks.apiFetch.mockImplementation(async (path: string, options?: RequestInit) => {
      if (path.startsWith('/projects?')) return page([firstProject])
      if (path === '/projects/categories?include_inactive=true') return []
      if (path === '/projects/project-1' && options?.method === 'DELETE') {
        return { deleted: true }
      }
      if (path === '/projects/project-1') return { ...firstProject }
      throw new Error(`Unexpected path: ${path}`)
    })
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)

    renderPage()
    await screen.findByLabelText('Project name')
    fireEvent.click(screen.getByRole('button', { name: 'Delete project' }))

    await waitFor(() =>
      expect(mocks.apiFetch).toHaveBeenCalledWith('/projects/project-1', {
        method: 'DELETE',
        headers: { 'X-Action-Confirm': 'CONFIRM' },
      })
    )
    expect(confirm).toHaveBeenCalledWith('Delete project: First project?')
    expect(mocks.toastSuccess).toHaveBeenCalledWith('Project deleted.')
    confirm.mockRestore()
  })

  it('sorts projects by the nearest due or review date and formats it in German', async () => {
    const undated = project('undated', 'Undated project')
    const later = { ...project('later', 'Later project'), due_date: '2026-08-20' }
    const nearestReview = {
      ...project('review', 'Review project'),
      preview_due_date: '2026-08-05',
    }
    const projectItems = [undated, later, nearestReview]
    mocks.apiFetch.mockImplementation(async (path: string) => {
      if (path.startsWith('/projects?')) return page(projectItems)
      if (path === '/projects/categories?include_inactive=true') return []
      if (path.startsWith('/projects/')) {
        const id = path.split('/').at(-1)
        return projectItems.find((item) => item.id === id)
      }
      throw new Error(`Unexpected path: ${path}`)
    })

    renderPage()

    const projectList = await screen.findByRole('complementary', { name: 'Projects' })
    const projectButtons = within(projectList).getAllByRole('button')
    expect(projectButtons.map((button) => button.textContent)).toEqual([
      expect.stringContaining('Review project'),
      expect.stringContaining('Later project'),
      expect.stringContaining('Undated project'),
    ])
    expect(projectButtons[0]).toHaveTextContent('05.08.2026')
    expect(projectButtons[1]).toHaveTextContent('20.08.2026')
    expect(projectButtons[2]).toHaveTextContent('—')
  })
})
