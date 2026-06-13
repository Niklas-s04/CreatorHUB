import { expect, test } from '@playwright/test'

import { loginAsAdmin } from './helpers'

test.describe('CSV Import E2E', () => {
  test('rejects malformed CSV payloads with a helpful error', async ({ page }) => {
    await loginAsAdmin(page)

    const response = await page.request.post('/api/products/import/csv', {
      data: {
        csv_text: 'title;brand\nCamera;Canon\nBrokenRow',
        delimiter: ';',
        quotechar: '"',
        column_map: { title: 'title', brand: 'brand' },
        defaults: {
          condition: 'good',
          current_value: 120,
          currency: 'EUR',
        },
        dry_run: true,
        idempotency_mode: 'skip_existing',
        continue_on_error: true,
      },
    })

    expect(response.status()).toBe(400)
    const body = await response.json()
    expect(String(body.detail)).toContain('missing_required_field_mappings')
  })
})
