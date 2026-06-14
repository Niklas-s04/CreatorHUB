import { useEffect, useState } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from 'react-router-dom'
import {
  confirmPasswordReset,
  getBootstrapStatus,
  login,
  requestPasswordReset,
  requestRegistration,
  setupAdminPassword,
} from '../../../../api'
import { authFormSchema, type AuthFormValues } from '../../../../shared/forms/schemas'
import { useUnsavedChangesWarning } from '../../../../shared/forms/useUnsavedChangesWarning'
import {
  getErrorKind,
  getErrorMessage,
  getValidationFieldErrors,
  type ErrorKind,
} from '../../../../shared/lib/errors'
import { InlineHint } from '../../../../shared/ui/states/InlineHint'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'
import { useI18n } from '../../../../shared/i18n/i18n'
import { AppLogo } from '../../../../shared/ui/brand/AppLogo'

type PasswordFieldProps = {
  id: string
  label: string
  registration: UseFormRegisterReturn
  error?: string
  value: string
  visible: boolean
  toggleLabel: string
  autoComplete: string
  onToggle: () => void
}

function EyeIcon({ off }: { off: boolean }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" focusable="false">
      <path
        d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      <path
        d="M12 9.2a2.8 2.8 0 1 1 0 5.6 2.8 2.8 0 0 1 0-5.6Z"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="1.8"
      />
      {off && (
        <path
          d="M4 4l16 16"
          fill="none"
          stroke="currentColor"
          strokeLinecap="round"
          strokeWidth="1.8"
        />
      )}
    </svg>
  )
}

function PasswordField({
  id,
  label,
  registration,
  error,
  value,
  visible,
  toggleLabel,
  autoComplete,
  onToggle,
}: PasswordFieldProps) {
  const showToggle = value.length > 0
  const errorId = `${id}-error`

  return (
    <div>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <div className="password-field">
        <input
          id={id}
          className="w100 auth-input"
          type={visible ? 'text' : 'password'}
          autoComplete={autoComplete}
          {...registration}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
        />
        {showToggle && (
          <button
            className="password-toggle"
            type="button"
            onClick={onToggle}
            aria-label={toggleLabel}
            aria-pressed={visible}
          >
            <EyeIcon off={visible} />
          </button>
        )}
      </div>
      {error && (
        <div id={errorId} className="error mt8" role="alert">
          {error}
        </div>
      )}
    </div>
  )
}

export default function LoginPage() {
  const nav = useNavigate()
  const toast = useToast()
  const { t } = useI18n()
  const [err, setErr] = useState<string | null>(null)
  const [errKind, setErrKind] = useState<ErrorKind>('technical')
  const [msg, setMsg] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [adminUsername, setAdminUsername] = useState('admin')
  const [showBootstrapPanel, setShowBootstrapPanel] = useState(false)
  const [bootstrapAvailable, setBootstrapAvailable] = useState(true)
  const [passwordVisible, setPasswordVisible] = useState(false)
  const [password2Visible, setPassword2Visible] = useState(false)

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
  const password = watch('password')
  const password2 = watch('password2')
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
        setShowBootstrapPanel(true)
        const status = await getBootstrapStatus(token)
        setAdminUsername(status.admin_username)
        setValue('bootstrapToken', token, { shouldDirty: false })
        if (status.needs_password_setup) {
          setMode('setup')
          setValue('username', status.admin_username, { shouldDirty: false })
        } else {
          setBootstrapAvailable(false)
          setShowBootstrapPanel(false)
          localStorage.removeItem('bootstrap_token')
          setValue('bootstrapToken', '', { shouldDirty: false })
        }
      } catch {}
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
        setBootstrapAvailable(false)
        setShowBootstrapPanel(false)
        reset(undefined, { keepValues: false })
        toast.success(t('login.adminPasswordSet'))
        nav('/admin')
      } else if (values.mode === 'register') {
        await requestRegistration(values.username, values.password)
        setMsg(t('login.registrationRequested'))
        toast.success(t('login.registrationRequested'))
        reset({ ...getValues(), password: '', password2: '' })
      } else if (values.mode === 'reset') {
        if (values.resetToken.trim()) {
          await confirmPasswordReset(values.resetToken, values.password)
          setMsg(t('login.passwordResetCompleteHint'))
          toast.success(t('login.passwordResetComplete'))
          setMode('login')
          reset({ ...getValues(), mode: 'login', password: '', password2: '', resetToken: '' })
        } else {
          await requestPasswordReset(values.username)
          setMsg(t('login.resetFallback'))
          toast.success(t('login.resetRequested'))
        }
      } else {
        await login(values.username, values.password, values.otp)
        reset(undefined, { keepValues: false })
        toast.success(t('login.loginSuccess'))
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
      if (!bootstrapToken.trim()) throw new Error(t('login.bootstrapMissing'))
      const status = await getBootstrapStatus(bootstrapToken)
      if (!status.needs_password_setup) {
        setMsg(t('login.bootstrapAlreadyDone'))
        setBootstrapAvailable(false)
        setShowBootstrapPanel(false)
        localStorage.removeItem('bootstrap_token')
        setValue('bootstrapToken', '', { shouldDirty: false })
        return
      }
      setAdminUsername(status.admin_username)
      setMode('setup')
      setValue('username', status.admin_username, { shouldDirty: false })
      setMsg(t('login.bootstrapReady'))
      toast.success(t('login.bootstrapReadyToast'))
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErrKind(getErrorKind(e))
      setErr(message)
      toast.error(message)
    }
  }

  return (
    <main className="login-shell">
      <div className="login-stage">
        <aside className="login-brand-panel" aria-label={t('login.brandSubline')}>
          <div className="login-brand-mark">
            <AppLogo compact />
          </div>
          <div>
            <p className="login-eyebrow">{t('login.brandSubline')}</p>
            <h1 className="login-hero-title">{t('login.heroTitle')}</h1>
            <p className="login-hero-copy">{t('login.heroCopy')}</p>
          </div>
          <div className="login-signal-grid" aria-hidden="true">
            <span>Ops</span>
            <span>Content</span>
            <span>Assets</span>
            <span>Audit</span>
          </div>
        </aside>

        <section className="login-card" aria-labelledby="login-title">
          <div className="login-card-head">
            <div>
              <p className="login-eyebrow">{t('login.welcomeBack')}</p>
              <h2 id="login-title" className="login-title">
                {mode === 'setup' ? t('login.setupTitle') : t('login.title')}
              </h2>
            </div>
            <span className="login-badge">{t('login.brandSubline')}</span>
          </div>

          {mode !== 'setup' && (
            <div className="mode-switch" aria-label={t('login.authMode')}>
              <button
                className={`mode-tab ${mode === 'login' ? 'active' : ''}`}
                type="button"
                aria-pressed={mode === 'login'}
                onClick={() => setMode('login')}
              >
                {t('login.modeLogin')}
              </button>
              <button
                className={`mode-tab ${mode === 'register' ? 'active' : ''}`}
                type="button"
                aria-pressed={mode === 'register'}
                onClick={() => setMode('register')}
              >
                {t('login.modeRegister')}
              </button>
              <button
                className={`mode-tab ${mode === 'reset' ? 'active' : ''}`}
                type="button"
                aria-pressed={mode === 'reset'}
                onClick={() => setMode('reset')}
              >
                {t('login.modeReset')}
              </button>
            </div>
          )}

          {bootstrapAvailable && mode !== 'setup' && (
            <div className="setup-entry">
              {!showBootstrapPanel ? (
                <button
                  className="setup-entry-button"
                  type="button"
                  onClick={() => setShowBootstrapPanel(true)}
                >
                  {t('login.firstSetup')}
                </button>
              ) : (
                <div className="setup-panel">
                  <div className="setup-panel-head">
                    <div>
                      <div className="setup-panel-title">{t('login.firstSetup')}</div>
                      <label htmlFor="auth-bootstrap-token" className="field-label">
                        {t('login.bootstrapTokenLabel')}
                      </label>
                    </div>
                    <button
                      className="setup-panel-close"
                      type="button"
                      onClick={() => setShowBootstrapPanel(false)}
                      aria-label={t('login.closeSetup')}
                    >
                      x
                    </button>
                  </div>
                  <div className="setup-panel-form">
                    <input
                      id="auth-bootstrap-token"
                      className="w100 auth-input"
                      {...register('bootstrapToken')}
                      aria-invalid={Boolean(errors.bootstrapToken?.message)}
                      aria-describedby={
                        errors.bootstrapToken?.message ? 'auth-bootstrap-token-error' : undefined
                      }
                      onChange={(e) => {
                        const value = e.target.value
                        setValue('bootstrapToken', value, {
                          shouldValidate: true,
                          shouldDirty: true,
                        })
                        localStorage.setItem('bootstrap_token', value)
                      }}
                      placeholder={t('login.bootstrapTokenPlaceholder')}
                    />
                    <button className="btn primary" type="button" onClick={checkBootstrap}>
                      {t('login.checkBootstrap')}
                    </button>
                  </div>
                  {errors.bootstrapToken?.message && (
                    <div id="auth-bootstrap-token-error" className="error mt8" role="alert">
                      {errors.bootstrapToken.message}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="login-context">
            {mode === 'setup'
              ? t('login.setupHint', { adminUsername })
              : mode === 'register'
                ? t('login.registerInfo')
                : mode === 'reset'
                  ? t('login.resetHint')
                  : t('login.loginHint')}
          </div>

          <form onSubmit={handleSubmit(onSubmit)} className="stack login-form">
            <input type="hidden" {...register('mode')} />
            {mode === 'setup' && <input type="hidden" {...register('bootstrapToken')} />}
            <div>
              <label htmlFor="auth-username" className="field-label">
                {t('login.username')}
              </label>
              {mode === 'setup' ? (
                <input
                  id="auth-username"
                  className="w100 auth-input"
                  value={adminUsername}
                  disabled
                  readOnly
                />
              ) : (
                <input
                  id="auth-username"
                  className="w100 auth-input"
                  autoComplete="username"
                  {...register('username')}
                  aria-invalid={Boolean(errors.username?.message)}
                  aria-describedby={errors.username?.message ? 'auth-username-error' : undefined}
                />
              )}
              {errors.username?.message && (
                <div id="auth-username-error" className="error mt8" role="alert">
                  {errors.username.message}
                </div>
              )}
            </div>

            <PasswordField
              id="auth-password"
              label={t('login.password')}
              registration={register('password')}
              error={errors.password?.message}
              value={password}
              visible={passwordVisible}
              toggleLabel={passwordVisible ? t('login.hidePassword') : t('login.showPassword')}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              onToggle={() => setPasswordVisible((value) => !value)}
            />

            {mode === 'login' && (
              <div>
                <label htmlFor="auth-otp" className="field-label">
                  {t('login.otp')}
                </label>
                <input
                  id="auth-otp"
                  className="w100 auth-input"
                  autoComplete="one-time-code"
                  {...register('otp')}
                  placeholder={t('login.otpPlaceholder')}
                />
              </div>
            )}

            {(mode === 'setup' || mode === 'register' || mode === 'reset') && (
              <PasswordField
                id="auth-password2"
                label={t('login.passwordRepeat')}
                registration={register('password2')}
                error={errors.password2?.message}
                value={password2}
                visible={password2Visible}
                toggleLabel={password2Visible ? t('login.hidePassword') : t('login.showPassword')}
                autoComplete="new-password"
                onToggle={() => setPassword2Visible((value) => !value)}
              />
            )}

            {mode === 'reset' && (
              <div>
                <label htmlFor="auth-reset-token" className="field-label">
                  {t('login.resetToken')}
                </label>
                <input
                  id="auth-reset-token"
                  className="w100 auth-input"
                  {...register('resetToken')}
                  placeholder={t('login.resetTokenPlaceholder')}
                />
              </div>
            )}

            {err && <InlineHint type={errKind} message={err} />}
            {msg && (
              <div className="muted" role="status" aria-live="polite">
                {msg}
              </div>
            )}

            <button className="btn primary w100 login-submit" disabled={busy}>
              {busy
                ? '...'
                : mode === 'setup'
                  ? t('login.submitSetup')
                  : mode === 'register'
                    ? t('login.submitRegister')
                    : mode === 'reset'
                      ? resetToken.trim()
                        ? t('login.submitResetConfirm')
                        : t('login.submitResetRequest')
                      : t('login.submitLogin')}
            </button>
          </form>
        </section>
      </div>
    </main>
  )
}
