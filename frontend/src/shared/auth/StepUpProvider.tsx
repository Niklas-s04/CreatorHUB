import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { getMfaStatus, performMfaStepUp, setStepUpHandler } from '../../api'
import { getErrorMessage } from '../lib/errors'
import { useI18n } from '../i18n/i18n'

type Resolver = {
  resolve: () => void
  reject: (error: Error) => void
}

type DialogState = {
  open: boolean
  loadingStatus: boolean
  mfaEnabled: boolean | null
  code: string
  error: string | null
  submitting: boolean
}

const initialState: DialogState = {
  open: false,
  loadingStatus: false,
  mfaEnabled: null,
  code: '',
  error: null,
  submitting: false,
}

export function StepUpProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const { language } = useI18n()
  const [state, setState] = useState<DialogState>(initialState)
  const pendingRef = useRef<Promise<void> | null>(null)
  const resolverRef = useRef<Resolver | null>(null)
  const isEnglish = language === 'en'

  useEffect(() => {
    setStepUpHandler(() => {
      if (pendingRef.current) return pendingRef.current

      const promise = new Promise<void>((resolve, reject) => {
        resolverRef.current = { resolve, reject }
      })
      pendingRef.current = promise
      setState({ ...initialState, open: true, loadingStatus: true })

      getMfaStatus()
        .then(status => {
          setState(prev => ({
            ...prev,
            loadingStatus: false,
            mfaEnabled: status.enabled,
          }))
        })
        .catch(error => {
          setState(prev => ({
            ...prev,
            loadingStatus: false,
            error: getErrorMessage(error),
          }))
        })

      return promise.finally(() => {
        pendingRef.current = null
      })
    })

    return () => {
      setStepUpHandler(null)
      resolverRef.current?.reject(new Error('Step-up authentication cancelled'))
    }
  }, [])

  function closeWithRejection() {
    resolverRef.current?.reject(new Error('Step-up authentication cancelled'))
    resolverRef.current = null
    setState(initialState)
  }

  function goToSettings() {
    closeWithRejection()
    navigate('/settings')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const code = state.code.trim()
    if (!code) {
      setState(prev => ({
        ...prev,
        error: isEnglish ? 'Enter an MFA code.' : 'MFA-Code eingeben.',
      }))
      return
    }

    try {
      setState(prev => ({ ...prev, submitting: true, error: null }))
      await performMfaStepUp(code)
      resolverRef.current?.resolve()
      resolverRef.current = null
      setState(initialState)
    } catch (error: unknown) {
      setState(prev => ({
        ...prev,
        submitting: false,
        error: getErrorMessage(error),
      }))
    }
  }

  return (
    <>
      {children}
      {state.open && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="step-up-title">
            <div className="page-header no-margin">
              <div>
                <h3 id="step-up-title">
                  {isEnglish ? 'Confirm sensitive action' : 'Sensible Aktion bestätigen'}
                </h3>
                <div className="muted small">
                  {isEnglish
                    ? 'Enter a current TOTP or recovery code.'
                    : 'Gib einen aktuellen TOTP- oder Recovery-Code ein.'}
                </div>
              </div>
            </div>

            {state.loadingStatus && (
              <div className="muted section-gap">{isEnglish ? 'Checking MFA status...' : 'MFA-Status wird geprüft...'}</div>
            )}

            {!state.loadingStatus && state.mfaEnabled === false && (
              <div className="section-gap">
                <div className="error">
                  {isEnglish
                    ? 'MFA must be enabled before this action can continue.'
                    : 'MFA muss aktiviert sein, bevor diese Aktion fortgesetzt werden kann.'}
                </div>
                <div className="table-actions mt8">
                  <button type="button" className="btn primary" onClick={goToSettings}>
                    {isEnglish ? 'Open settings' : 'Einstellungen öffnen'}
                  </button>
                  <button type="button" className="btn" onClick={closeWithRejection}>
                    {isEnglish ? 'Cancel' : 'Abbrechen'}
                  </button>
                </div>
              </div>
            )}

            {!state.loadingStatus && state.mfaEnabled !== false && (
              <form onSubmit={submit} className="section-gap">
                <label htmlFor="step-up-code" className="field-label">
                  {isEnglish ? 'MFA code' : 'MFA-Code'}
                </label>
                <input
                  id="step-up-code"
                  className="full-width"
                  autoFocus
                  value={state.code}
                  onChange={event => setState(prev => ({ ...prev, code: event.target.value }))}
                  placeholder={isEnglish ? 'TOTP or recovery code' : 'TOTP oder Recovery-Code'}
                  autoComplete="one-time-code"
                />
                {state.error && <div className="error mt8" role="alert">{state.error}</div>}
                <div className="table-actions mt8">
                  <button className="btn primary" disabled={state.submitting}>
                    {state.submitting ? '...' : isEnglish ? 'Confirm' : 'Bestätigen'}
                  </button>
                  <button type="button" className="btn" onClick={closeWithRejection} disabled={state.submitting}>
                    {isEnglish ? 'Cancel' : 'Abbrechen'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  )
}
