import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useUnsavedChangesWarning } from './useUnsavedChangesWarning'

vi.mock('react-router-dom', () => ({
  useBeforeUnload: vi.fn(),
}))

import { useBeforeUnload } from 'react-router-dom'

describe('useUnsavedChangesWarning', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('registers beforeunload protection only while dirty', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const removeSpy = vi.spyOn(window, 'removeEventListener')

    const { rerender, unmount } = renderHook(({ dirty }) => useUnsavedChangesWarning(dirty), {
      initialProps: { dirty: false },
    })

    expect(useBeforeUnload).toHaveBeenCalled()
    expect(addSpy).not.toHaveBeenCalled()

    rerender({ dirty: true })
    expect(addSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function))

    unmount()
    expect(removeSpy).toHaveBeenCalledWith('beforeunload', expect.any(Function))
  })
})
