import { useEffect } from 'react'
import { useBeforeUnload } from 'react-router-dom'

const DEFAULT_MESSAGE = 'Du hast ungespeicherte Änderungen. Wirklich verlassen?'

export function useUnsavedChangesWarning(isDirty: boolean, message = DEFAULT_MESSAGE) {
  useBeforeUnload(
    event => {
      if (!isDirty) return
      event.preventDefault()
      event.returnValue = message
    },
    { capture: true }
  )

  useEffect(() => {
    if (!isDirty) return

    const beforeUnloadHandler = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = message
      return message
    }

    window.addEventListener('beforeunload', beforeUnloadHandler)
    return () => window.removeEventListener('beforeunload', beforeUnloadHandler)
  }, [isDirty, message])
}
