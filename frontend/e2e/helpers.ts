import crypto from 'node:crypto'

import { expect, Page } from '@playwright/test'

export const E2E_ADMIN_USER = process.env.E2E_ADMIN_USER || 'admin'
export const E2E_ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'test_admin_password_1234567890'
export const E2E_BOOTSTRAP_TOKEN =
  process.env.E2E_BOOTSTRAP_TOKEN || 'test_bootstrap_token_1234567890'
export const E2E_API_BASE = process.env.E2E_API_BASE || '/api/v1'

export function e2eApiPath(path: string): string {
  return `${E2E_API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}

export function uniqueSuffix(prefix: string): string {
  const stamp = Date.now().toString(36)
  const rnd = Math.floor(Math.random() * 100_000).toString(36)
  return `${prefix}_${stamp}_${rnd}`
}

async function seedNecessaryCookieConsent(page: Page): Promise<void> {
  await page.addInitScript(() => {
    window.localStorage.setItem('consent_level', 'necessary')
  })
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
  await seedNecessaryCookieConsent(page)
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Login' })).toBeVisible()
  await acceptNecessaryCookies(page)
}

export async function acceptNecessaryCookies(page: Page): Promise<void> {
  const banner = page.locator('.cookie-consent')
  const visible = await banner.isVisible({ timeout: 2000 }).catch(() => false)
  if (!visible) return

  const button = page.getByRole('button', { name: /necessary only|nur notwendige cookies/i })
  await button.click()
  await expect(banner).toBeHidden()
}

async function submitLogin(page: Page, username: string, password: string): Promise<void> {
  const form = page.locator('form')
  await form.getByLabel('Username').fill(username)
  await form.getByLabel('Password').first().fill(password)
  await form.getByRole('button').last().click()
}

export async function login(page: Page, username: string, password: string): Promise<void> {
  await gotoLogin(page)
  const loginResponsePromise = page
    .waitForResponse(
      (response) =>
        response.request().method() === 'POST' &&
        response.url().includes(e2eApiPath('/auth/token')),
      { timeout: 15000 }
    )
    .catch(() => null)
  await submitLogin(page, username, password)
  const loginResponse = await loginResponsePromise

  const reachedProtected = await page
    .waitForURL(/\/($|dashboard|admin|products|assets|content|email|settings)/, { timeout: 10000 })
    .then(() => true)
    .catch(() => false)

  if (!reachedProtected) {
    const inlineError = await page
      .locator('.error')
      .first()
      .textContent({ timeout: 1000 })
      .catch(() => null)
    const statusHint = await page
      .locator('[role="status"]')
      .first()
      .textContent({ timeout: 1000 })
      .catch(() => null)
    const responseDetails = loginResponse
      ? `HTTP ${loginResponse.status()}: ${await loginResponse.text().catch(() => 'unreadable response')}`
      : 'no login response observed'
    throw new Error(
      `E2E login failed and stayed on /login. ${responseDetails}. Error: ${inlineError ?? 'unknown'}. Hint: ${statusHint ?? 'none'}`
    )
  }
}

async function ensureAdminBootstrap(page: Page): Promise<void> {
  const headers = { 'X-Bootstrap-Token': E2E_BOOTSTRAP_TOKEN }
  const statusResponse = await page.request.get(e2eApiPath('/auth/bootstrap-status'), { headers })

  if (statusResponse.status() === 404) return
  if (!statusResponse.ok()) {
    throw new Error(
      `Unable to inspect E2E admin bootstrap state (HTTP ${statusResponse.status()}): ${await statusResponse.text()}`
    )
  }

  const status = (await statusResponse.json()) as { needs_password_setup?: boolean }
  if (!status.needs_password_setup) return

  const setupResponse = await page.request.post(e2eApiPath('/auth/setup-admin-password'), {
    headers,
    data: { password: E2E_ADMIN_PASSWORD },
  })
  if (![200, 404, 409].includes(setupResponse.status())) {
    throw new Error(
      `Unable to initialize the E2E admin password (HTTP ${setupResponse.status()}): ${await setupResponse.text()}`
    )
  }

  // The setup endpoint also creates an authenticated session. Clear it so the
  // login helper still verifies the real interactive login flow.
  await page.context().clearCookies()
}

export async function loginAsAdmin(page: Page): Promise<void> {
  await ensureAdminBootstrap(page)
  await login(page, E2E_ADMIN_USER, E2E_ADMIN_PASSWORD)
}

export async function csrfHeaders(page: Page): Promise<Record<string, string>> {
  const csrf = (await page.context().cookies()).find((cookie) => cookie.name === 'creatorhub_csrf')
  return csrf ? { 'X-CSRF-Token': csrf.value } : {}
}

export async function logout(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Logout' }).click()
  await expect(page).toHaveURL(/\/login/)
}

export async function registerViaUi(page: Page, username: string, password: string): Promise<void> {
  await gotoLogin(page)
  await page.getByRole('button', { name: 'Registrieren' }).click()

  const form = page.locator('form')
  await form.getByLabel('Username').fill(username)
  const pwInputs = form.locator('input[type="password"]')
  await pwInputs.nth(0).fill(password)
  await pwInputs.nth(1).fill(password)

  await page.getByRole('button', { name: 'Anfrage senden' }).click()
  await expect(
    page.getByRole('main').getByText(/Registrierungsanfrage (wurde an den Admin gesendet|gesendet)/)
  ).toBeVisible()
}

export async function approveRegistrationAsAdmin(page: Page, username: string): Promise<void> {
  await loginAsAdmin(page)
  await page.goto('/admin')

  const row = page
    .locator('tr', { hasText: username })
    .filter({ has: page.getByRole('button', { name: 'Freigeben' }) })
  await expect(row).toBeVisible({ timeout: 15000 })
  await row.getByRole('button', { name: 'Freigeben' }).click()
  await expect(row).toHaveCount(0)
}
