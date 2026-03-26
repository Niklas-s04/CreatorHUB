import { createContext, useCallback, useContext, useMemo, useState } from 'react'

type ToastVariant = 'success' | 'error'

type ToastItem = {
  id: number
  message: string
  variant: ToastVariant
}

type ToastContextValue = {
  success: (message: string) => void
  error: (message: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])

  const push = useCallback((message: string, variant: ToastVariant) => {
    const id = Date.now() + Math.floor(Math.random() * 1000)
    setToasts(prev => [...prev, { id, message, variant }])
    setTimeout(() => {
      setToasts(prev => prev.filter(item => item.id !== id))
    }, 3500)
  }, [])

  const value = useMemo<ToastContextValue>(() => ({
    success: message => push(message, 'success'),
    error: message => push(message, 'error'),
  }), [push])

  const successToasts = toasts.filter(toast => toast.variant === 'success')
  const errorToasts = toasts.filter(toast => toast.variant === 'error')

  function dismissToast(id: number) {
    setToasts(prev => prev.filter(item => item.id !== id))
  }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-viewport" role="region" aria-label="Statusmeldungen">
        <div aria-live="polite" aria-atomic="true">
          {successToasts.map(toast => (
            <div key={toast.id} className={`toast ${toast.variant}`} role="status">
              <span>{toast.message}</span>
              <button type="button" className="toast-close" onClick={() => dismissToast(toast.id)} aria-label="Meldung schließen">×</button>
            </div>
          ))}
        </div>
        <div aria-live="assertive" aria-atomic="true">
          {errorToasts.map(toast => (
            <div key={toast.id} className={`toast ${toast.variant}`} role="alert">
              <span>{toast.message}</span>
              <button type="button" className="toast-close" onClick={() => dismissToast(toast.id)} aria-label="Fehlermeldung schließen">×</button>
            </div>
          ))}
        </div>
      </div>
    </ToastContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast muss innerhalb von ToastProvider verwendet werden')
  }
  return context
}
