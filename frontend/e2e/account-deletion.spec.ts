import { expect, test } from '@playwright/test'

import { generateTotpCode, loginAsAdmin, logout, uniqueSuffix } from './helpers'

test.describe('Account deletion E2E', () => {
  test('user can request account deletion after MFA step-up and is logged out immediately', async ({
    page,
  }) => {
    const username = uniqueSuffix('delete_me')
    const password = 'Delete!Pass12345'

    await loginAsAdmin(page)
    const createResponse = await page.request.post('/api/auth/users', {
      data: {
        username,
        password,
        role: 'viewer',
      },
    })
    expect(createResponse.status()).toBe(200)
    await logout(page)

    await page.goto('/login')
    const form = page.locator('form')
    await form.locator('input').nth(0).fill(username)
    await form.locator('input[type="password"]').first().fill(password)
    await form.locator('button').last().click()
    await expect(page).toHaveURL(/\/(dashboard|products|settings|admin)/)

    await page.goto('/settings')
    await expect(page.getByText(/Account (löschen|lÃ¶schen)/)).toBeVisible({ timeout: 15000 })

    await page.getByRole('button', { name: 'TOTP-Secret erzeugen' }).click()
    const secretText = await page.getByText(/^Secret:/).textContent()
    expect(secretText).toBeTruthy()
    const secret = secretText!.replace(/^Secret:\s*/, '').trim()
    await page.locator('#settings-mfa-enable-code').fill(generateTotpCode(secret))
    await page.getByRole('button', { name: 'MFA aktivieren' }).click()
    await expect(page.getByText('MFA wurde aktiviert')).toBeVisible({ timeout: 15000 })

    await page.locator('#settings-delete-account-confirm').fill('LÃ–SCHEN')
    await page.getByRole('button', { name: /Account zur (Löschung|LÃ¶schung) anmelden/ }).click()

    const stepUpDialog = page.getByRole('dialog', { name: /Sensible Aktion bestätigen/i })
    if (await stepUpDialog.isVisible().catch(() => false)) {
      await stepUpDialog.getByLabel('MFA-Code').fill(generateTotpCode(secret))
      await stepUpDialog.getByRole('button', { name: 'Bestätigen' }).click()
    }

    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible()

    const meResponse = await page.request.get('/api/auth/me')
    expect(meResponse.status()).toBe(401)
  })
})
