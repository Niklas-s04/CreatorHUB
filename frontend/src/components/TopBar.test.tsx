import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

import TopBar from './TopBar'

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
})
