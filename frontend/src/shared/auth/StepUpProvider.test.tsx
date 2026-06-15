import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { apiFetch, setStepUpHandler } from '../../api'
import { LanguageProvider } from '../i18n/i18n'
import { StepUpProvider } from './StepUpProvider'

function Trigger() {
  async function run() {
    const response = await apiFetch<{ ok: boolean }>('/sensitive', { method: 'POST' })
    if (response.ok) {
      document.body.dataset.stepUpResult = 'ok'
    }
  }

  return <button onClick={() => void run()}>Run sensitive action</button>
}

describe('StepUpProvider', () => {
  beforeEach(() => {
    setStepUpHandler(null)
    delete document.body.dataset.stepUpResult
    vi.stubGlobal('fetch', vi.fn())
  })

  it('prompts for MFA and retries the blocked request', async () => {
    const fetchMock = vi.mocked(fetch)
    fetchMock
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: 'Step-up authentication required' }), {
          status: 403,
          headers: { 'content-type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ enabled: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ mfa_verified: true, step_up_expires_at: '2026-06-13T22:00:00Z' }),
          {
            status: 200,
            headers: { 'content-type': 'application/json' },
          }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        })
      )

    render(
      <MemoryRouter>
        <LanguageProvider>
          <StepUpProvider>
            <Trigger />
          </StepUpProvider>
        </LanguageProvider>
      </MemoryRouter>
    )

    fireEvent.click(screen.getByRole('button', { name: 'Run sensitive action' }))

    await waitFor(() => expect(screen.getByRole('dialog')).toBeInTheDocument())
    fireEvent.change(screen.getByLabelText('MFA-Code'), { target: { value: '123456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Bestätigen' }))

    await waitFor(() => expect(document.body.dataset.stepUpResult).toBe('ok'))
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      '/api/v1/sensitive',
      '/api/v1/auth/mfa/status',
      '/api/v1/auth/mfa/step-up',
      '/api/v1/sensitive',
    ])
  })
})
