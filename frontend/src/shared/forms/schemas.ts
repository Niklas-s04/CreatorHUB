import { z } from 'zod'

export const authModeSchema = z.enum(['login', 'register', 'setup', 'reset'])

export const authFormSchema = z.object({
  mode: authModeSchema,
  username: z.string().trim().min(1, 'Username ist erforderlich'),
  password: z.string().min(1, 'Passwort ist erforderlich'),
  password2: z.string(),
  otp: z.string(),
  resetToken: z.string(),
  bootstrapToken: z.string(),
}).superRefine((data, ctx) => {
  const needsConfirmPassword = data.mode === 'register' || data.mode === 'setup' || data.mode === 'reset'
  if (needsConfirmPassword && data.password !== data.password2) {
    ctx.addIssue({
      path: ['password2'],
      code: z.ZodIssueCode.custom,
      message: 'Passwörter stimmen nicht überein',
    })
  }

  if (data.mode === 'setup' && !data.bootstrapToken.trim()) {
    ctx.addIssue({
      path: ['bootstrapToken'],
      code: z.ZodIssueCode.custom,
      message: 'Bootstrap-Token erforderlich',
    })
  }

  if (data.mode === 'reset' && data.resetToken.trim().length > 0 && data.password.length < 8) {
    ctx.addIssue({
      path: ['password'],
      code: z.ZodIssueCode.custom,
      message: 'Neues Passwort muss mindestens 8 Zeichen haben',
    })
  }

  if ((data.mode === 'register' || data.mode === 'setup') && data.password.length < 8) {
    ctx.addIssue({
      path: ['password'],
      code: z.ZodIssueCode.custom,
      message: 'Passwort muss mindestens 8 Zeichen haben',
    })
  }
})

export type AuthFormValues = z.infer<typeof authFormSchema>

export const productCreateSchema = z.object({
  title: z.string().trim().min(1, 'Titel ist erforderlich'),
  brand: z.string().trim(),
  model: z.string().trim(),
  currentValue: z.string().trim(),
}).superRefine((data, ctx) => {
  if (!data.currentValue) return
  const parsed = Number(data.currentValue.replace(',', '.'))
  if (!Number.isFinite(parsed)) {
    ctx.addIssue({
      path: ['currentValue'],
      code: z.ZodIssueCode.custom,
      message: 'Wert muss eine Zahl sein',
    })
    return
  }
  if (parsed < 0) {
    ctx.addIssue({
      path: ['currentValue'],
      code: z.ZodIssueCode.custom,
      message: 'Wert darf nicht negativ sein',
    })
  }
})

export type ProductCreateFormValues = z.infer<typeof productCreateSchema>

export const changePasswordSchema = z.object({
  currentPassword: z.string().min(1, 'Aktuelles Passwort ist erforderlich'),
  newPassword: z.string().min(8, 'Neues Passwort muss mindestens 8 Zeichen haben'),
})

export type ChangePasswordFormValues = z.infer<typeof changePasswordSchema>

export const mfaEnableSchema = z.object({
  code: z.string().trim().min(1, 'TOTP-Code ist erforderlich'),
})

export type MfaEnableFormValues = z.infer<typeof mfaEnableSchema>

export const mfaDisableSchema = z.object({
  password: z.string().trim().min(1, 'Passwort ist erforderlich'),
  code: z.string().trim().min(1, 'TOTP oder Recovery-Code ist erforderlich'),
})

export type MfaDisableFormValues = z.infer<typeof mfaDisableSchema>

export const knowledgeDocSchema = z.object({
  title: z.string().trim().min(1, 'Titel ist erforderlich'),
  content: z.string().trim().min(1, 'Inhalt ist erforderlich'),
})

export type KnowledgeDocFormValues = z.infer<typeof knowledgeDocSchema>
