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
    await page.getByRole('button', { name: 'Speichern' }).click()

    await expect(page.getByRole('link', { name: productTitle })).toBeVisible({ timeout: 15000 })
    await page.getByRole('link', { name: productTitle }).click()

    await expect(page.locator('.title-strong', { hasText: productTitle })).toBeVisible({
      timeout: 15000,
    })

    const notesArea = page.locator('.product-main textarea')
    await notesArea.fill('E2E-Notiz: aktualisiert')
    await page.getByRole('button', { name: 'Speichern' }).first().click()

    await page.locator('.product-main select').selectOption('sold')
    await page.getByPlaceholder('z.B. 120').fill('123')
    await page.getByRole('button', { name: 'Apply' }).click()
    await expect(page.locator('.product-main .pill', { hasText: 'sold' })).toBeVisible({
      timeout: 15000,
    })

    const uploadInput = page.locator('.product-side input[type="file"]').first()
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
