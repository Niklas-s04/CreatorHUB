import React, { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from 'react-router-dom'
import { confirmPasswordReset, getBootstrapStatus, login, requestPasswordReset, requestRegistration, setupAdminPassword } from '../../../../api'
import { authFormSchema, type AuthFormValues } from '../../../../shared/forms/schemas'
import { useUnsavedChangesWarning } from '../../../../shared/forms/useUnsavedChangesWarning'
import { getErrorKind, getErrorMessage, getValidationFieldErrors, type ErrorKind } from '../../../../shared/lib/errors'
import { InlineHint } from '../../../../shared/ui/states/InlineHint'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'

export default function LoginPage() {
  const nav = useNavigate()
  const toast = useToast()
  const [err, setErr] = useState<string | null>(null)
  const [errKind, setErrKind] = useState<ErrorKind>('technical')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [adminUsername, setAdminUsername] = useState('admin')

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    setError,
    reset,
    getValues,
    formState: { errors, isDirty },
  } = useForm<AuthFormValues>({
    resolver: zodResolver(authFormSchema),
    defaultValues: {
      mode: 'login',
      username: 'admin',
      password: '',
      password2: '',
      otp: '',
      resetToken: '',
      bootstrapToken: '',
    },
  })

  const mode = watch('mode')
  const bootstrapToken = watch('bootstrapToken')
  const resetToken = watch('resetToken')
  useUnsavedChangesWarning(isDirty && !busy)

  function setMode(nextMode: AuthFormValues['mode']) {
    setValue('mode', nextMode, { shouldValidate: true, shouldDirty: false })
    setErr(null)
    setErrKind('technical')
    setMsg(null)
  }

  useEffect(() => {
    ;(async () => {
      try {
        const token = localStorage.getItem('bootstrap_token') || ''
        if (!token) return
        const status = await getBootstrapStatus(token)
        setAdminUsername(status.admin_username)
        setValue('bootstrapToken', token, { shouldDirty: false })
        if (status.needs_password_setup) {
          setMode('setup')
          setValue('username', status.admin_username, { shouldDirty: false })
        }
      } catch {
      }
    })()
  }, [setValue])

  async function onSubmit(values: AuthFormValues) {
    setErr(null)
    setMsg(null)
    setBusy(true)
    try {
      if (values.mode === 'setup') {
        await setupAdminPassword(values.password, values.bootstrapToken)
        localStorage.removeItem('bootstrap_token')
        reset(undefined, { keepValues: false })
        toast.success('Admin-Passwort wurde gesetzt')
        nav('/admin')
      } else if (values.mode === 'register') {
        await requestRegistration(values.username, values.password)
        setMsg('Registrierungsanfrage wurde an den Admin gesendet.')
        toast.success('Registrierungsanfrage gesendet')
        reset({ ...getValues(), password: '', password2: '' })
      } else if (values.mode === 'reset') {
        if (values.resetToken.trim()) {
          await confirmPasswordReset(values.resetToken, values.password)
          setMsg('Passwort wurde zurückgesetzt. Bitte einloggen.')
          toast.success('Passwort wurde zurückgesetzt')
          setMode('login')
          reset({ ...getValues(), mode: 'login', password: '', password2: '', resetToken: '' })
        } else {
          const res = await requestPasswordReset(values.username)
          setMsg(res.reset_token ? `Reset-Token: ${res.reset_token}` : 'Falls der Benutzer existiert, wurde ein Reset ausgelöst.')
          toast.success('Passwort-Reset angefordert')
        }
      } else {
        await login(values.username, values.password, values.otp)
        reset(undefined, { keepValues: false })
        toast.success('Login erfolgreich')
        nav('/')
      }
    } catch (e: unknown) {
      setErrKind(getErrorKind(e))
      const fieldErrors = getValidationFieldErrors(e)
      Object.entries(fieldErrors).forEach(([field, message]) => {
        if (field in getValues()) {
          setError(field as keyof AuthFormValues, { message })
        }
      })
      if (!Object.keys(fieldErrors).length) {
        const message = getErrorMessage(e)
        setErr(message)
        toast.error(message)
      }
    } finally {
      setBusy(false)
    }
  }

  async function checkBootstrap() {
    setErr(null)
    setErrKind('technical')
    setMsg(null)
    try {
      if (!bootstrapToken.trim()) throw new Error('Bootstrap-Token erforderlich')
      const status = await getBootstrapStatus(bootstrapToken)
      if (!status.needs_password_setup) {
        setMsg('Erstsetup bereits abgeschlossen.')
        return
      }
      setAdminUsername(status.admin_username)
      setMode('setup')
      setValue('username', status.admin_username, { shouldDirty: false })
      setMsg('Erstsetup freigeschaltet.')
      toast.success('Erstsetup freigeschaltet')
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  return (
    <div className="login-shell">
      <div className="card login-card">
        <div className="page-header no-margin">
          <h2 className="page-title">Login</h2>
          <span className="muted small">CreatorHUB</span>
        </div>

        {mode !== 'setup' && (
          <div className="mode-switch">
            <button className={`btn ${mode === 'login' ? 'primary' : ''}`} type="button" onClick={() => setMode('login')}>Login</button>
            <button className={`btn ${mode === 'register' ? 'primary' : ''}`} type="button" onClick={() => setMode('register')}>Registrieren</button>
            <button className={`btn ${mode === 'reset' ? 'primary' : ''}`} type="button" onClick={() => setMode('reset')}>Passwort-Reset</button>
          </div>
        )}

        <div className="section-gap">
          <label htmlFor="auth-bootstrap-token" className="field-label">Bootstrap-Token (nur Erstsetup)</label>
          <input
            id="auth-bootstrap-token"
            className="w100"
            {...register('bootstrapToken')}
            aria-invalid={Boolean(errors.bootstrapToken?.message)}
            aria-describedby={errors.bootstrapToken?.message ? 'auth-bootstrap-token-error' : undefined}
            onChange={e => {
              const value = e.target.value
              setValue('bootstrapToken', value, { shouldValidate: true, shouldDirty: true })
              localStorage.setItem('bootstrap_token', value)
            }}
            placeholder="Install-Token"
          />
          {errors.bootstrapToken?.message && <div id="auth-bootstrap-token-error" className="error mt8" role="alert">{errors.bootstrapToken.message}</div>}
          <button className="btn mt8" type="button" onClick={checkBootstrap}>Erstsetup prüfen</button>
        </div>

        {mode === 'setup' ? (
          <div className="muted small">Erststart: Admin-Passwort für Benutzer {adminUsername} setzen.</div>
        ) : (
          <div className="muted small">Bei Registrierung wird eine Anfrage an den Admin gestellt.</div>
        )}

        <hr />

        <form onSubmit={handleSubmit(onSubmit)} className="stack">
          <input type="hidden" {...register('mode')} />
          <div>
            <label htmlFor="auth-username" className="field-label">Username</label>
            {mode === 'setup' ? (
              <input id="auth-username" className="w100" value={adminUsername} disabled readOnly />
            ) : (
              <input
                id="auth-username"
                className="w100"
                {...register('username')}
                aria-invalid={Boolean(errors.username?.message)}
                aria-describedby={errors.username?.message ? 'auth-username-error' : undefined}
              />
            )}
            {errors.username?.message && <div id="auth-username-error" className="error mt8" role="alert">{errors.username.message}</div>}
          </div>

          <div>
            <label htmlFor="auth-password" className="field-label">Password</label>
            <input
              id="auth-password"
              className="w100"
              type="password"
              {...register('password')}
              aria-invalid={Boolean(errors.password?.message)}
              aria-describedby={errors.password?.message ? 'auth-password-error' : undefined}
            />
            {errors.password?.message && <div id="auth-password-error" className="error mt8" role="alert">{errors.password.message}</div>}
          </div>

          {mode === 'login' && (
            <div>
              <label htmlFor="auth-otp" className="field-label">MFA-Code (optional)</label>
              <input id="auth-otp" className="w100" {...register('otp')} placeholder="TOTP oder Recovery-Code" />
            </div>
          )}

          {(mode === 'setup' || mode === 'register' || mode === 'reset') && (
            <div>
              <label htmlFor="auth-password2" className="field-label">Password wiederholen</label>
              <input
                id="auth-password2"
                className="w100"
                type="password"
                {...register('password2')}
                aria-invalid={Boolean(errors.password2?.message)}
                aria-describedby={errors.password2?.message ? 'auth-password2-error' : undefined}
              />
              {errors.password2?.message && <div id="auth-password2-error" className="error mt8" role="alert">{errors.password2.message}</div>}
            </div>
          )}

          {mode === 'reset' && (
            <div>
              <label htmlFor="auth-reset-token" className="field-label">Reset-Token (optional für Bestätigung)</label>
              <input id="auth-reset-token" className="w100" {...register('resetToken')} placeholder="Token einfügen, um neues Passwort zu setzen" />
            </div>
          )}

          {err && <InlineHint type={errKind} message={err} />}
          {msg && <div className="muted" role="status" aria-live="polite">{msg}</div>}

          <button className="btn primary w100" disabled={busy}>
            {busy ? '...' : mode === 'setup' ? 'Admin-Passwort setzen' : mode === 'register' ? 'Anfrage senden' : mode === 'reset' ? (resetToken.trim() ? 'Passwort setzen' : 'Reset anfordern') : 'Login'}
          </button>
        </form>
      </div>
    </div>
  )
}