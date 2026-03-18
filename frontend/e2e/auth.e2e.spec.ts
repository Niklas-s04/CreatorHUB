import { expect, test } from '@playwright/test'

import { E2E_ADMIN_PASSWORD, E2E_ADMIN_USER, loginAsAdmin, logout } from './helpers'

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
})
