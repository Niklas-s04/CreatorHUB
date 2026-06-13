import crypto from 'node:crypto'

import { expect, Page } from '@playwright/test'

export const E2E_ADMIN_USER = process.env.E2E_ADMIN_USER || 'admin'
export const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'Admin!Pass12345'
export const E2E_BOOTSTRAP_TOKEN = process.env.E2E_BOOTSTRAP_TOKEN || ''

export function uniqueSuffix(prefix: string): string {
  const stamp = Date.now().toString(36)
  const rnd = Math.floor(Math.random() * 100_000).toString(36)
  return `${prefix}_${stamp}_${rnd}`
}

function decodeBase32(secret: string): Buffer {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  const normalized = secret.replace(/=+$/g, '').replace(/\s+/g, '').toUpperCase()
  let bits = ''

  for (const char of normalized) {
    const index = alphabet.indexOf(char)
    if (index < 0) {
      throw new Error(`Invalid base32 character: ${char}`)
    }
    bits += index.toString(2).padStart(5, '0')
  }

  const bytes: number[] = []
  for (let offset = 0; offset + 8 <= bits.length; offset += 8) {
    bytes.push(Number.parseInt(bits.slice(offset, offset + 8), 2))
  }

  return Buffer.from(bytes)
}

export function generateTotpCode(secret: string, time = Date.now()): string {
  const counter = Math.floor(time / 30_000)
  const counterBuffer = Buffer.alloc(8)
  counterBuffer.writeBigUInt64BE(BigInt(counter))

  const hmac = crypto.createHmac('sha1', decodeBase32(secret))
  hmac.update(counterBuffer)
  const digest = hmac.digest()
  const offset = digest[digest.length - 1] & 0x0f
  return ((digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000).toString().padStart(6, '0')
}

export async function gotoLogin(page: Page): Promise<void> {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible()
}

async function submitLogin(page: Page, username: string, password: string): Promise<void> {
  const form = page.locator('form')
  await form.getByLabel('Username').fill(username)
  await form.getByLabel('Password').first().fill(password)
  await form.getByRole('button').last().click()
}

async function setupAdminPassword(page: Page, password: string): Promise<void> {
  if (!E2E_BOOTSTRAP_TOKEN) {
    throw new Error('Admin password setup required, but E2E_BOOTSTRAP_TOKEN is not set.')
  }

  await page.getByPlaceholder(/Install-Token|Install token/i).fill(E2E_BOOTSTRAP_TOKEN)
  await page.getByRole('button', { name: /Erstsetup prüfen|Check first setup/i }).click()

  const form = page.locator('form')
  await form.getByLabel('Password').first().fill(password)
  await form.getByLabel(/Password wiederholen|Repeat password/i).fill(password)

  await page.getByRole('button', { name: /Admin-Passwort setzen|Set admin password/i }).click()
}

export async function login(page: Page, username: string, password: string): Promise<void> {
  await gotoLogin(page)
  await submitLogin(page, username, password)

  const onProtectedRoute = await page
    .waitForURL(/\/(dashboard|admin|products|assets|content|email|settings)/, { timeout: 2500 })
    .then(() => true)
    .catch(() => false)

  if (!onProtectedRoute) {
    const setupVisible = await page
      .getByRole('button', { name: /Admin-Passwort setzen|Set admin password/i })
      .isVisible()
      .catch(() => false)

    if (setupVisible || E2E_BOOTSTRAP_TOKEN) {
      await setupAdminPassword(page, password)
    }
  }

  const reachedProtected = await page
    .waitForURL(/\/(dashboard|admin|products|assets|content|email|settings)/, { timeout: 10000 })
    .then(() => true)
    .catch(() => false)

  if (!reachedProtected) {
    const inlineError = await page
      .locator('.error')
      .first()
      .textContent()
      .catch(() => null)
    const statusHint = await page
      .locator('[role="status"]')
      .first()
      .textContent()
      .catch(() => null)
    throw new Error(
      `E2E login failed and stayed on /login. Error: ${inlineError ?? 'unknown'}. Hint: ${statusHint ?? 'none'}`
    )
  }
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
