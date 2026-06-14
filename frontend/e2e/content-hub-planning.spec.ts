import { expect, test, type Page } from '@playwright/test'

import { loginAsAdmin, uniqueSuffix } from './helpers'

async function createTemplate(page: Page, templateName: string, firstItemTitle: string) {
  await page.getByRole('tab', { name: /Vorlagen|Templates/i }).click()
  const templateCreateCard = page
    .locator('.card')
    .filter({ hasText: /Vorlage erstellen|Create template/i })
    .first()
  await templateCreateCard.locator('input').nth(0).fill(templateName)
  await templateCreateCard.locator('input').nth(1).fill(firstItemTitle)
  await templateCreateCard.getByRole('button', { name: /Speichern|Save/i }).click()
  await expect(page.locator('.card.tight strong', { hasText: templateName }).first()).toBeVisible({
    timeout: 15_000,
  })
}

async function createItemOnBoard(page: Page, videoTitle: string) {
  await page.getByRole('tab', { name: /Plan/i }).click()
  await page.locator('#content-new-title').fill(videoTitle)
  await page.locator('.page-actions select').nth(0).selectOption('youtube')
  await page.locator('.page-actions select').nth(1).selectOption('review')
  await page.locator('.page-actions .btn.primary').first().click()
  await expect(page.locator('.kanban-card', { hasText: videoTitle }).first()).toBeVisible({
    timeout: 15_000,
  })
  await page.locator('.kanban-card', { hasText: videoTitle }).first().click()
}

async function getLoginBlocker(page: Page): Promise<string | null> {
  try {
    await loginAsAdmin(page)
    return null
  } catch (error) {
    return error instanceof Error ? error.message : String(error)
  }
}

test.describe('Content Hub planning E2E', () => {
  test('Plan -> Template -> Checklist -> Readiness ist sichtbar und konsistent', async ({
    page,
  }) => {
    const videoTitle = uniqueSuffix('E2E Video Plan')
    const templateName = uniqueSuffix('E2E Checklist')

    const loginBlocker = await getLoginBlocker(page)
    test.skip(Boolean(loginBlocker), `Content Hub E2E skipped: ${loginBlocker ?? ''}`)
    if (loginBlocker) return
    await page.goto('/content')

    await createTemplate(page, templateName, 'Recording done')
    await createItemOnBoard(page, videoTitle)

    // Apply template in checklist tab.
    await page.getByRole('tab', { name: /Checkliste|Checklist/i }).click()
    await page
      .getByRole('button', { name: new RegExp(`(Anwenden|Apply):\\s*${templateName}`) })
      .click()

    await expect(page.getByText(/Readiness/i)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/Publish ready/i)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/Required checklist tasks are open/i)).toBeVisible({
      timeout: 15_000,
    })

    // Verify generated task is visible in board details.
    await page.getByRole('tab', { name: /Plan/i }).click()
    await page.locator('.kanban-card', { hasText: videoTitle }).first().click()
    await expect(page.getByText('Recording done')).toBeVisible({ timeout: 15_000 })
  })

  test('Negativpfad: Publish bleibt blockiert solange required checklist tasks offen sind', async ({
    page,
  }) => {
    const videoTitle = uniqueSuffix('E2E Publish Guard')
    const templateName = uniqueSuffix('E2E Required Guard')

    const loginBlocker = await getLoginBlocker(page)
    test.skip(Boolean(loginBlocker), `Content Hub E2E skipped: ${loginBlocker ?? ''}`)
    if (loginBlocker) return
    await page.goto('/content')

    await createTemplate(page, templateName, 'Required publish step')
    await createItemOnBoard(page, videoTitle)

    await page.getByRole('tab', { name: /Checkliste|Checklist/i }).click()
    await page
      .getByRole('button', { name: new RegExp(`(Anwenden|Apply):\\s*${templateName}`) })
      .click()
    await expect(page.getByText(/Required checklist tasks are open/i)).toBeVisible({
      timeout: 15_000,
    })

    // Attempt to force status to published; backend should reject and UI should keep non-published status.
    await page.getByRole('tab', { name: /Plan/i }).click()
    await page.locator('.kanban-card', { hasText: videoTitle }).first().click()
    page.once('dialog', (dialog) => dialog.accept())
    await page.locator('.content-side select').first().selectOption('published')
    await expect(page.locator('.content-side select').first()).not.toHaveValue('published')

    await page.getByRole('tab', { name: /Checkliste|Checklist/i }).click()
    await expect(page.getByText(/Publish ready/i)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/Publish ready: (No|Nein)/i)).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText(/Required checklist tasks are open/i)).toBeVisible({
      timeout: 15_000,
    })
  })
})
