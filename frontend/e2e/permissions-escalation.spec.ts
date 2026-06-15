import { expect, test } from '@playwright/test'

import { csrfHeaders, e2eApiPath, login, loginAsAdmin, logout, uniqueSuffix } from './helpers'

test.describe('Permission boundary E2E', () => {
  test('viewer cannot see product write actions', async ({ page }) => {
    const viewerName = uniqueSuffix('viewer')
    const viewerPassword = 'Viewer!Pass12345'

    await loginAsAdmin(page)
    const createResponse = await page.request.post(e2eApiPath('/auth/users'), {
      headers: await csrfHeaders(page),
      data: {
        username: viewerName,
        password: viewerPassword,
        role: 'viewer',
      },
    })
    expect(createResponse.status()).toBe(200)

    await logout(page)
    await login(page, viewerName, viewerPassword)

    await page.goto('/products')
    await expect(page.getByRole('button', { name: '+ Produkt' })).toBeHidden()
    await expect(page.getByRole('button', { name: 'Export CSV' })).toBeHidden()
  })
})
