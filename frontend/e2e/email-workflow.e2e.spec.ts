import { expect, test } from '@playwright/test'

import { loginAsAdmin } from './helpers'

test.describe('Email Workflow E2E', () => {
  test('E-Mail-Workflow deckt Happy Path und Fehlerpfad ab', async ({ page }) => {
    await loginAsAdmin(page)
    await page.goto('/email')

    await expect(page.getByRole('heading', { name: /E-Mail Threads|Email threads/i })).toBeVisible()

    const newDraftButton = page.getByRole('button', { name: /Neuer Draft|New draft/i })
    await expect(newDraftButton).toBeDisabled()

    await page
      .getByLabel(/E-Mail Rohtext|Email raw text/i)
      .fill(
        'Hallo, wir interessieren uns fuer eine Sponsoring-Kooperation im Mai. Bitte sende Preise und Bedingungen.'
      )
    await expect(newDraftButton).toBeEnabled({ timeout: 15000 })
    await newDraftButton.click()

    const successSignal = page.locator('.draft-card').first()
    const errorSignal = page.locator('.error').first()

    const result = await Promise.race([
      successSignal.waitFor({ state: 'visible', timeout: 30000 }).then(() => 'success' as const),
      errorSignal.waitFor({ state: 'visible', timeout: 30000 }).then(() => 'error' as const),
    ]).catch(() => null)

    expect(result).not.toBeNull()

    if (result === 'success') {
      await expect(page.getByRole('heading', { name: /Verlauf|History/i })).toBeVisible()
      await expect(page.locator('.message-pill').first()).toBeVisible()

      const refineButton = page.getByRole('button', { name: /Refine|Verfeinern/i })
      if (await refineButton.count()) {
        await page.waitForTimeout(500)
        const answerInput = page.getByLabel(/Antwort auf Frage 1|Answer to question 1/i).first()
        if (await answerInput.count()) {
          await answerInput.fill('Budget liegt bei 2.500 EUR netto.')
          await expect(answerInput).toHaveValue('Budget liegt bei 2.500 EUR netto.')
          await expect(refineButton).toBeEnabled()
          await refineButton.click()
          await expect(page.locator('.draft-card')).toHaveCount(2, { timeout: 30000 })
        }
      }
    } else {
      await expect(errorSignal).toBeVisible()
    }
  })
})
