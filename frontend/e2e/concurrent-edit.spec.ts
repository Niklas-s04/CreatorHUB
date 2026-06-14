import { expect, test } from '@playwright/test'

import { csrfHeaders, loginAsAdmin, logout, uniqueSuffix } from './helpers'

test.describe('Concurrent edit E2E', () => {
  test('last write is persisted when two sessions edit the same product notes', async ({
    browser,
    page,
  }) => {
    const productTitle = uniqueSuffix('Concurrent Product')

    await loginAsAdmin(page)
    const createResponse = await page.request.post('/api/products', {
      headers: await csrfHeaders(page),
      data: { title: productTitle },
    })
    expect(createResponse.status()).toBe(200)
    const created = await createResponse.json()
    const productId = String(created.id)

    const editorContext = await browser.newContext()
    const editorPage = await editorContext.newPage()
    await loginAsAdmin(editorPage)

    await page.goto(`/products/${productId}`)
    await editorPage.goto(`/products/${productId}`)

    const notesA = page.getByLabel('Notizen')
    const notesB = editorPage.getByLabel('Notizen')

    await notesA.fill('Version A')
    await page.getByRole('button', { name: 'Stammdaten speichern' }).click()
    await expect(notesA).toHaveValue('Version A')

    await notesB.fill('Version B')
    await editorPage.getByRole('button', { name: 'Stammdaten speichern' }).click()
    await expect(notesB).toHaveValue('Version B')

    await page.reload()
    await expect(page.getByLabel('Notizen')).toHaveValue('Version B')

    await editorContext.close()
    await logout(page)
  })
})
