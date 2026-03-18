import { expect, test } from '@playwright/test'

import { approveRegistrationAsAdmin, login, logout, registerViaUi, uniqueSuffix } from './helpers'

const editorPassword = process.env.E2E_EDITOR_PASSWORD || 'Editor!Pass12345'

test.describe('Registration + Role Boundaries E2E', () => {
  test('Registrierungsfreigabe und Admin-Grenze für Editor', async ({ page }) => {
    const username = uniqueSuffix('editor')

    await registerViaUi(page, username, editorPassword)
    await approveRegistrationAsAdmin(page, username)
    await logout(page)

    await login(page, username, editorPassword)
    await page.goto('/admin')

    await expect(page.getByText('Nur Admin kann Registrierungsanfragen bearbeiten.')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Freigeben' })).toHaveCount(0)
  })
})
