import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router'

import TopBar from './TopBar'
import { apiFetch } from '../api'

vi.mock('../api', () => ({
  apiFetch: vi.fn(),
}))

const apiFetchMock = vi.mocked(apiFetch)

function LocationProbe() {
  const location = useLocation()
  return <span data-testid="location">{location.pathname}</span>
}

describe('TopBar', () => {
  beforeEach(() => {
    apiFetchMock.mockReset()
  })

  it('rendert Suchfeld und triggert Menü-Callback', () => {
    const onToggleMenu = vi.fn()

    render(
      <MemoryRouter>
        <TopBar onToggleMenu={onToggleMenu} />
      </MemoryRouter>
    )

    expect(screen.getByLabelText('Suchen')).toBeInTheDocument()
    expect(screen.getByLabelText('Benachrichtigungen')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Navigation öffnen'))
    expect(onToggleMenu).toHaveBeenCalledTimes(1)
  })

  it('zeigt gruppierte globale Treffer mit Highlight und Tastaturauswahl', async () => {
    apiFetchMock.mockImplementation(async (path) => {
      if (path === '/dashboard/summary') return { metrics: [] }
      if (path === '/auth/me') return { username: 'admin' }
      return {
        query: 'canon',
        total: 2,
        groups: [
          {
            type: 'product',
            label: 'Produkte',
            count: 1,
            hits: [
              {
                id: 'p1',
                type: 'product',
                title: 'Canon R6',
                subtitle: 'camera',
                detail_path: '/products/p1',
                score: 9.4,
              },
            ],
          },
          {
            type: 'asset',
            label: 'Assets',
            count: 1,
            hits: [
              {
                id: 'a1',
                type: 'asset',
                title: 'Canon Produktfoto',
                subtitle: 'image',
                detail_path: '/assets#asset-a1',
                score: 7.1,
              },
            ],
          },
        ],
      }
    })

    const { container } = render(
      <MemoryRouter>
        <TopBar onToggleMenu={() => undefined} />
      </MemoryRouter>
    )

    const input = screen.getByLabelText('Suchen')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'canon' } })

    await waitFor(() => expect(apiFetchMock).toHaveBeenCalled(), { timeout: 2000 })
    await waitFor(() => expect(screen.getByText('Produkte')).toBeInTheDocument())

    expect(screen.getByText('Assets')).toBeInTheDocument()
    expect(container.querySelectorAll('.topbar-search-mark').length).toBeGreaterThan(0)

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    expect(container.querySelector('.topbar-search-item.active')).toBeInTheDocument()
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    expect(container.querySelector('.topbar-search-item.active')).toBeInTheDocument()
  })

  it('verdrahtet Aktionsbuttons mit Routen und Live-Badges', async () => {
    apiFetchMock.mockImplementation(async (path) => {
      if (path === '/auth/me') return { username: 'niklas hub' }
      if (path === '/dashboard/summary') {
        return {
          metrics: [
            { key: 'pending_registration_requests', count: 2 },
            { key: 'unreviewed_assets', count: 3 },
            { key: 'overdue_tasks', count: 1 },
            { key: 'risky_email_drafts', count: 4 },
          ],
        }
      }
      return { groups: [] }
    })

    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <TopBar onToggleMenu={() => undefined} />
        <LocationProbe />
      </MemoryRouter>
    )

    expect(await screen.findByText('6')).toBeInTheDocument()
    expect(screen.getByText('4')).toBeInTheDocument()
    expect(await screen.findByText('NH')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Benachrichtigungen'))
    expect(screen.getByTestId('location')).toHaveTextContent('/operations')

    fireEvent.click(screen.getByLabelText('Nachrichten'))
    expect(screen.getByTestId('location')).toHaveTextContent('/email')

    fireEvent.click(screen.getByLabelText('Profil öffnen'))
    expect(screen.getByTestId('location')).toHaveTextContent('/settings')
  })

  it('zeigt einen neutralen Profil-Fallback, wenn /auth/me fehlschlägt', async () => {
    apiFetchMock.mockImplementation(async (path) => {
      if (path === '/dashboard/summary') return { metrics: [] }
      if (path === '/auth/me') throw new Error('not available')
      return { groups: [] }
    })

    const { container } = render(
      <MemoryRouter>
        <TopBar onToggleMenu={() => undefined} />
      </MemoryRouter>
    )

    await waitFor(() => expect(container.querySelector('.topbar-profile')).toHaveTextContent('?'))
  })
})
