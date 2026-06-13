import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test.describe('Accessibility smoke', () => {
  test('login page meets baseline WCAG checks and exposes consent actions', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible()
    await expect(
      page.getByRole('region', { name: /necessary cookies are required/i })
    ).toBeVisible()
    await expect(page.getByRole('button', { name: /necessary only/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /allow analytics/i })).toBeVisible()

    const accessibilityScanResults = await new AxeBuilder({ page })
      .disableRules(['color-contrast'])
      .analyze()
    expect(accessibilityScanResults.violations).toEqual([])
  })

  test('keyboard navigation can switch to register mode', async ({ page }) => {
    await page.goto('/login')

    const registerButton = page.getByRole('button', { name: 'Registrieren' })
    await registerButton.focus()
    await page.keyboard.press('Enter')

    await expect(page.getByLabel('Password wiederholen')).toBeVisible()
  })

  test('status updates are announced via aria-live region', async ({ page }) => {
    await page.goto('/login')

    await page.getByRole('button', { name: 'Passwort-Reset' }).click()
    await page.getByLabel('Username').fill('unknown-user')
    await page.getByLabel('Password').fill('StrongPass123!')
    await page.getByLabel('Password wiederholen').fill('StrongPass123!')
    await page.getByRole('button', { name: 'Reset anfordern' }).click()

    const status = page.locator('[role="status"][aria-live="polite"]')
    await expect(status).toBeVisible({ timeout: 15000 })
  })
})
