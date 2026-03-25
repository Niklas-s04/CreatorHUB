import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import TopBar from './TopBar'
import { apiFetch } from '../api'

vi.mock('../api', () => ({
  apiFetch: vi.fn(),
}))

const apiFetchMock = vi.mocked(apiFetch)

describe('TopBar', () => {
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
    apiFetchMock.mockResolvedValue({
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
})
