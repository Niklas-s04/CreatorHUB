import { expect, Page } from '@playwright/test'

export const E2E_ADMIN_USER = process.env.E2E_ADMIN_USER || 'admin'
export const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'Admin!Pass12345'
export const E2E_BOOTSTRAP_TOKEN = process.env.E2E_BOOTSTRAP_TOKEN || ''

export function uniqueSuffix(prefix: string): string {
  const stamp = Date.now().toString(36)
  const rnd = Math.floor(Math.random() * 100_000).toString(36)
  return `${prefix}_${stamp}_${rnd}`
}

export async function gotoLogin(page: Page): Promise<void> {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible()
}

async function submitLogin(page: Page, username: string, password: string): Promise<void> {
  const form = page.locator('form')
  await form.locator('input').nth(0).fill(username)
  await form.locator('input[type="password"]').first().fill(password)
  await form.locator('button').last().click()
}

async function setupAdminPassword(page: Page, password: string): Promise<void> {
  if (!E2E_BOOTSTRAP_TOKEN) {
    throw new Error('Admin password setup required, but E2E_BOOTSTRAP_TOKEN is not set.')
  }

  await page.getByPlaceholder('Install-Token').fill(E2E_BOOTSTRAP_TOKEN)
  await page.getByRole('button', { name: 'Erstsetup prüfen' }).click()

  const pwInputs = page.locator('input[type="password"]')
  await pwInputs.nth(0).fill(password)
  await pwInputs.nth(1).fill(password)

  await page.getByRole('button', { name: 'Admin-Passwort setzen' }).click()
}

export async function login(page: Page, username: string, password: string): Promise<void> {
  await gotoLogin(page)
  await submitLogin(page, username, password)

  if (
    await page
      .getByText('Admin password setup required')
      .isVisible({ timeout: 1200 })
      .catch(() => false)
  ) {
    await setupAdminPassword(page, password)
  }

  await expect(page).toHaveURL(/\/(dashboard|admin|products|assets|content|email|settings)/)
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await login(page, E2E_ADMIN_USER, E2E_ADMIN_PASSWORD)
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page).toHaveURL(/\/login/)
}

export async function registerViaUi(page: Page, username: string, password: string): Promise<void> {
  await gotoLogin(page)
  await page.getByRole('button', { name: 'Registrieren' }).click()

  const form = page.locator('form')
  await form.locator('input').nth(0).fill(username)
  const pwInputs = form.locator('input[type="password"]')
  await pwInputs.nth(0).fill(password)
  await pwInputs.nth(1).fill(password)

  await page.getByRole('button', { name: 'Anfrage senden' }).click()
  await expect(page.getByText('Registrierungsanfrage wurde an den Admin gesendet.')).toBeVisible()
}

export async function approveRegistrationAsAdmin(page: Page, username: string): Promise<void> {
  await loginAsAdmin(page)
  await page.goto('/admin')

  const row = page.locator('tr', { hasText: username })
  await expect(row).toBeVisible({ timeout: 15000 })
  await row.getByRole('button', { name: 'Freigeben' }).click()
  await expect(row).toHaveCount(0)
}
