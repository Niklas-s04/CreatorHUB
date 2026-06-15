/// <reference types="node" />

import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

const nginxConfig = readFileSync(resolve(process.cwd(), 'nginx.conf'), 'utf8')

function getFrontendCsp(): string {
  const match = nginxConfig.match(/add_header\s+Content-Security-Policy\s+"([^"]+)"/)
  if (!match) throw new Error('Content-Security-Policy header not found in frontend nginx.conf')
  return match[1]
}

describe('frontend nginx security headers', () => {
  it('keeps CSP protections without forcing HTTP assets to HTTPS', () => {
    const csp = getFrontendCsp()

    expect(csp).not.toContain('upgrade-insecure-requests')
    expect(csp).toContain("default-src 'self'")
    expect(csp).toContain("script-src 'self'")
    expect(csp).toContain("style-src 'self'")
    expect(csp).toContain("img-src 'self' blob: data:")
    expect(csp).toContain("connect-src 'self'")
    expect(csp).toContain("font-src 'self'")
    expect(csp).toContain("base-uri 'self'")
    expect(csp).toContain("frame-ancestors 'none'")
    expect(csp).toContain("object-src 'none'")
    expect(csp).toContain("form-action 'self'")
  })
})
