import { fireEvent, render, screen } from '@testing-library/react'

import TopBar from './TopBar'

describe('TopBar', () => {
  it('rendert Suchfeld und triggert Menü-Callback', () => {
    const onToggleMenu = vi.fn()

    render(<TopBar onToggleMenu={onToggleMenu} />)

    expect(screen.getByLabelText('Suchen')).toBeInTheDocument()
    expect(screen.getByLabelText('Benachrichtigungen')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Navigation öffnen'))
    expect(onToggleMenu).toHaveBeenCalledTimes(1)
  })
})
