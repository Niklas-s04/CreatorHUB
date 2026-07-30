import { expect, test } from '@playwright/test'

import { loginAsAdmin, uniqueSuffix } from './helpers'

const PNG_BYTES = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGNk+M/wn4GBgYGJAQoAHhgCAu/QjeYAAAAASUVORK5CYII=',
  'base64'
)

test.describe('Products + Assets E2E', () => {
  test('Produkt anlegen, bearbeiten und Asset-Review durchführen', async ({ page }) => {
    const productTitle = uniqueSuffix('E2E Produkt')

    await loginAsAdmin(page)
    await page.goto('/products')

    await page.getByRole('button', { name: '+ Produkt' }).click()
    await page.getByPlaceholder('Titel*').fill(productTitle)
    await page.getByRole('button', { name: 'Speichern', exact: true }).click()

    await expect(page.getByRole('link', { name: productTitle })).toBeVisible({ timeout: 15000 })
    await page.getByRole('link', { name: productTitle }).click()

    await expect(page.getByLabel('Titel').first()).toHaveValue(productTitle, {
      timeout: 15000,
    })

    await page.getByLabel('Notizen').fill('E2E-Notiz: aktualisiert')
    await page.getByRole('button', { name: 'Stammdaten speichern' }).click()
    await expect(page.getByLabel('Notizen')).toHaveValue('E2E-Notiz: aktualisiert')
    await page.waitForTimeout(500)

    const statusSelect = page.getByRole('combobox').nth(2)
    await statusSelect.selectOption('sold')
    await expect(statusSelect).toHaveValue('sold')
    await page.getByPlaceholder('z.B. 120').fill('123')
    await expect(page.getByPlaceholder('z.B. 120')).toHaveValue('123')
    await page.getByRole('button', { name: /Status anwenden|Apply/ }).click()
    await expect(statusSelect).toHaveValue('sold')
    await expect(page.getByText('123 EUR').first()).toBeVisible({ timeout: 15000 })

    const uploadInput = page.locator('input[type="file"]').first()
    await uploadInput.setInputFiles({
      name: 'e2e.png',
      mimeType: 'image/png',
      buffer: PNG_BYTES,
    })

    const approveButton = page.getByRole('button', { name: 'Approve' }).first()
    await expect(approveButton).toBeVisible({ timeout: 20000 })
    await approveButton.click()

    await expect(page.locator('.grid .muted.small', { hasText: 'approved' }).first()).toBeVisible({
      timeout: 15000,
    })
  })
})
