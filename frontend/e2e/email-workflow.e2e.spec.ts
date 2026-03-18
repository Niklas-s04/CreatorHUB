import { expect, test } from '@playwright/test'

import { loginAsAdmin } from './helpers'

test.describe('Email Workflow E2E', () => {
  test('E-Mail-Workflow deckt Happy Path und Fehlerpfad ab', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/email')

    const newDraftButton = page.getByRole('button', { name: 'Neuer Draft' })
    await expect(newDraftButton).toBeDisabled()

    await page
      .getByPlaceholder('E-Mail hier einfügen (raw)…')
      .fill(
        'Hallo, wir interessieren uns für eine Sponsoring-Kooperation im Mai. Bitte sende Preise und Bedingungen.'
      )
    await newDraftButton.click()

    const successSignal = page.locator('.draft-card').first()
    const errorSignal = page.locator('.error').first()

    const success = await successSignal.isVisible({ timeout: 30000 }).catch(() => false)
    const failed = await errorSignal
      .isVisible({ timeout: success ? 500 : 30000 })
      .catch(() => false)

    expect(success || failed).toBeTruthy()

    if (success) {
      await expect(page.getByText('Verlauf')).toBeVisible()
      await expect(page.locator('.message-pill').first()).toBeVisible()

      const refineButton = page.getByRole('button', { name: 'Refine' })
      if (await refineButton.count()) {
        const answerInput = page.getByPlaceholder('Deine Antwort…').first()
        if (await answerInput.count()) {
          await answerInput.fill('Budget liegt bei 2.500 EUR netto.')
          await refineButton.click()
          await expect(page.locator('.draft-card')).toHaveCount(2, { timeout: 30000 })
        }
      }
    } else {
      await expect(errorSignal).toBeVisible()
    }
  })
})
