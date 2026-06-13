import { describe, expect, it } from 'vitest'
import {
  authFormSchema,
  changePasswordSchema,
  knowledgeDocSchema,
  mfaDisableSchema,
  mfaEnableSchema,
  productCreateSchema,
} from './schemas'

describe('form schemas', () => {
  it('validates auth flows with mode-specific rules', () => {
    expect(authFormSchema.safeParse({ mode: 'login', username: 'alice', password: 'x', password2: '', otp: '', resetToken: '', bootstrapToken: '' }).success).toBe(true)
    expect(authFormSchema.safeParse({ mode: 'register', username: 'alice', password: 'short', password2: 'short', otp: '', resetToken: '', bootstrapToken: '' }).success).toBe(false)
    expect(authFormSchema.safeParse({ mode: 'setup', username: 'alice', password: 'secret12', password2: 'secret12', otp: '', resetToken: '', bootstrapToken: '  ' }).success).toBe(false)
    expect(authFormSchema.safeParse({ mode: 'reset', username: 'alice', password: 'short', password2: 'short', otp: '', resetToken: 'token', bootstrapToken: '' }).success).toBe(false)
    expect(authFormSchema.safeParse({ mode: 'register', username: 'alice', password: 'secret12', password2: 'secret12', otp: '', resetToken: '', bootstrapToken: '' }).success).toBe(true)
  })

  it('validates product and password forms', () => {
    expect(productCreateSchema.safeParse({ title: 'Cam', brand: '', model: '', currentValue: '' }).success).toBe(true)
    expect(productCreateSchema.safeParse({ title: 'Cam', brand: '', model: '', currentValue: 'abc' }).success).toBe(false)
    expect(productCreateSchema.safeParse({ title: 'Cam', brand: '', model: '', currentValue: '-10' }).success).toBe(false)
    expect(changePasswordSchema.safeParse({ currentPassword: 'old', newPassword: '12345678' }).success).toBe(true)
    expect(mfaEnableSchema.safeParse({ code: '123456' }).success).toBe(true)
    expect(mfaDisableSchema.safeParse({ password: 'secret', code: '123456' }).success).toBe(true)
  })

  it('requires an outdated reason for knowledge docs', () => {
    expect(knowledgeDocSchema.safeParse({
      title: 'Doc',
      content: 'Text',
      sourceName: '',
      sourceUrl: '',
      sourceType: 'internal',
      sourceReviewStatus: 'approved',
      sourceReviewNote: '',
      originSummary: '',
      trustLevel: 'high',
      isOutdated: true,
      outdatedReason: '',
    }).success).toBe(false)

    expect(knowledgeDocSchema.safeParse({
      title: 'Doc',
      content: 'Text',
      sourceName: '',
      sourceUrl: '',
      sourceType: 'internal',
      sourceReviewStatus: 'approved',
      sourceReviewNote: '',
      originSummary: '',
      trustLevel: 'high',
      isOutdated: false,
      outdatedReason: '',
    }).success).toBe(true)
  })
})