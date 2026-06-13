import { expect, test } from '@playwright/test'

import {
  E2E_ADMIN_PASSWORD,
  E2E_ADMIN_USER,
  generateTotpCode,
  loginAsAdmin,
  logout,
} from './helpers'

test.describe('Auth E2E', () => {
  test('zeigt Fehlerszenario bei ungültigem Login', async ({ page }) => {
    await page.goto('/login')

    const form = page.locator('form')
    await form.locator('input').nth(0).fill(E2E_ADMIN_USER)
    await form.locator('input[type="password"]').first().fill('definitiv-falsch')
    await form.locator('button').last().click()

    await expect(page.locator('.error')).toBeVisible()
  })

  test('kritischer Happy Path: Login und Logout', async ({ page }) => {
    await loginAsAdmin(page)
    await expect(page.getByText('Dashboard')).toBeVisible()

    await logout(page)

    const form = page.locator('form')
    await form.locator('input').nth(0).fill(E2E_ADMIN_USER)
    await form.locator('input[type="password"]').first().fill(E2E_ADMIN_PASSWORD)
    await form.locator('button').last().click()
    await expect(page).toHaveURL(/\/(dashboard|admin)/)
  })

  test('Account kann nach MFA-Step-up gelöscht werden', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/settings')

    await page.getByRole('button', { name: 'TOTP-Secret erzeugen' }).click()
    const secretText = await page.getByText(/^Secret:/).textContent()
    expect(secretText).toBeTruthy()
    const secret = secretText!.replace(/^Secret:\s*/, '').trim()
    const totp = generateTotpCode(secret)

    await page.locator('#settings-mfa-enable-code').fill(totp)
    await page.getByRole('button', { name: 'MFA aktivieren' }).click()
    await expect(page.getByText('MFA wurde aktiviert')).toBeVisible({ timeout: 15000 })

    await page.locator('#settings-delete-account-confirm').fill('LÃ–SCHEN')
    await page.getByRole('button', { name: /Account zur (Löschung|LÃ¶schung) anmelden/ }).click()

    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible()
  })
})
