import { expect, test } from '@playwright/test'

import { loginAsAdmin, logout, uniqueSuffix } from './helpers'

test.describe('Permission boundary E2E', () => {
  test('viewer cannot see product write actions', async ({ page }) => {
    const viewerName = uniqueSuffix('viewer')
    const viewerPassword = 'Viewer!Pass12345'

    await loginAsAdmin(page)
    const createResponse = await page.request.post('/api/auth/users', {
      data: {
        username: viewerName,
        password: viewerPassword,
        role: 'viewer',
      },
    })
    expect(createResponse.status()).toBe(200)

    await logout(page)
    await page.goto('/login')
    const form = page.locator('form')
    await form.locator('input').nth(0).fill(viewerName)
    await form.locator('input[type="password"]').first().fill(viewerPassword)
    await form.locator('button').last().click()

    await page.goto('/products')
    await expect(page.getByRole('button', { name: '+ Produkt' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Export CSV' })).toBeDisabled()
  })
})
