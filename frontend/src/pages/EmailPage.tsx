import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { useRateCardDoc } from '../hooks/useRateCardDoc'

type EmailTone = 'short' | 'neutral' | 'friendly' | 'firm'

type EmailThreadSummary = {
  id: string
  subject: string | null
  raw_body: string
  detected_intent: string
  created_at: string
  updated_at: string
}

type EmailDraft = {
  id: string
  thread_id: string
  tone: EmailTone
  draft_subject: string | null
  draft_body: string
  questions_to_ask: string | null
  risk_flags: string | null
  approved: boolean
  created_at: string
  updated_at: string
}

type EmailThreadMessage = {
  id: string
  thread_id: string
  role: 'user' | 'assistant' | 'system'
  content: string | null
  payload?: Record<string, any> | null
  created_at: string
}

type DealDraftStatus = 'intake' | 'review' | 'negotiating' | 'won' | 'lost'

type DealDraft = {
  id: string
  thread_id: string | null
  brand_name: string | null
  contact_name: string | null
  contact_email: string | null
  budget: string | null
  deliverables: string | null
  usage_rights: string | null
  deadlines: string | null
  notes: string | null
  status: DealDraftStatus
  created_at: string
  updated_at: string
}

type DealDraftFormState = {
  brand_name: string
  contact_name: string
  contact_email: string
  budget: string
  deliverables: string
  usage_rights: string
  deadlines: string
  notes: string
  status: DealDraftStatus
}

type EmailThreadDetail = EmailThreadSummary & {
  drafts: EmailDraft[]
  messages: EmailThreadMessage[]
  deal_draft: DealDraft | null
}

type AnswersState = Record<number, string>

type ThreadsResponse = EmailThreadSummary[]

const toneOptions: { value: EmailTone; label: string }[] = [
  { value: 'short', label: 'short' },
  { value: 'neutral', label: 'neutral' },
  { value: 'friendly', label: 'friendly' },
  { value: 'firm', label: 'firm' },
]

const dealStatusOptions: { value: DealDraftStatus; label: string }[] = [
  { value: 'intake', label: 'Intake' },
  { value: 'review', label: 'Review' },
  { value: 'negotiating', label: 'Negotiating' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

const dealFieldKeys: (keyof Omit<DealDraftFormState, 'status'>)[] = [
  'brand_name',
  'contact_name',
  'contact_email',
  'budget',
  'deliverables',
  'usage_rights',
  'deadlines',
  'notes',
]

function buildDealFormState(draft: DealDraft | null): DealDraftFormState {
  return {
    brand_name: draft?.brand_name || '',
    contact_name: draft?.contact_name || '',
    contact_email: draft?.contact_email || '',
    budget: draft?.budget || '',
    deliverables: draft?.deliverables || '',
    usage_rights: draft?.usage_rights || '',
    deadlines: draft?.deadlines || '',
    notes: draft?.notes || '',
    status: draft?.status || 'intake',
  }
}

function formatDate(value?: string) {
  if (!value) return ''
  try {
    return new Date(value).toLocaleString()
  } catch (e) {
    return value
  }
}

function safeParseList(value: string | null): string[] {
  if (!value) return []
  try {
    const arr = JSON.parse(value)
    return Array.isArray(arr) ? arr : []
  } catch (e) {
    return []
  }
}

export default function EmailPage() {
  const [subject, setSubject] = useState('')
  const [raw, setRaw] = useState('')
  const [tone, setTone] = useState<EmailTone>('neutral')

  const [threads, setThreads] = useState<ThreadsResponse>([])
  const [threadsLoading, setThreadsLoading] = useState(false)

  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [threadDetail, setThreadDetail] = useState<EmailThreadDetail | null>(null)
  const [threadLoading, setThreadLoading] = useState(false)
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null)
  const [compareDraftId, setCompareDraftId] = useState<string | null>(null)

  const [answers, setAnswers] = useState<AnswersState>({})
  const [note, setNote] = useState('')

  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [refining, setRefining] = useState(false)
  const { doc: rateCardDoc, loading: rateCardLoading } = useRateCardDoc()
  const [dealForm, setDealForm] = useState<DealDraftFormState>(() => buildDealFormState(null))
  const [dealSaving, setDealSaving] = useState(false)
  const [dealAutoLoading, setDealAutoLoading] = useState(false)
  const [dealErr, setDealErr] = useState<string | null>(null)

  useEffect(() => {
    loadThreads()
  }, [])

  useEffect(() => {
    setAnswers({})
    setNote('')
  }, [activeDraftId])

  useEffect(() => {
    setDealForm(buildDealFormState(threadDetail?.deal_draft || null))
    setDealErr(null)
  }, [threadDetail?.deal_draft?.id, threadDetail?.id])

  async function loadThreads() {
    setThreadsLoading(true)
    try {
      const data = await apiFetch('/email/threads?limit=50') as ThreadsResponse
      setThreads(data)
      if (!selectedThreadId && data.length) {
        await selectThread(data[0].id)
      }
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setThreadsLoading(false)
    }
  }

  async function selectThread(id: string, focusDraftId?: string) {
    setSelectedThreadId(id)
    setCompareDraftId(null)
    await loadThreadDetail(id, focusDraftId)
  }

  async function loadThreadDetail(id: string, focusDraftId?: string) {
    setThreadLoading(true)
    try {
      const detail = await apiFetch(`/email/threads/${id}`) as EmailThreadDetail
      setThreadDetail(detail)
      const fallback = detail.drafts.length ? detail.drafts[0].id : null
      setActiveDraftId(focusDraftId || fallback)
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setThreadLoading(false)
    }
  }

  useEffect(() => {
    if (!threadDetail || !activeDraftId) {
      setCompareDraftId(null)
      return
    }
    const drafts = threadDetail.drafts
    const activeIdx = drafts.findIndex(d => d.id === activeDraftId)
    if (activeIdx === -1) {
      setCompareDraftId(null)
      return
    }
    const fallback = drafts[activeIdx + 1] || drafts.find(d => d.id !== activeDraftId)
    if (!fallback) {
      setCompareDraftId(null)
      return
    }
    if (!compareDraftId || compareDraftId === activeDraftId || !drafts.some(d => d.id === compareDraftId)) {
      setCompareDraftId(fallback.id)
    }
  }, [threadDetail, activeDraftId, compareDraftId])

  async function generate() {
    if (!raw.trim()) return
    setBusy(true)
    setErr(null)
    try {
      const draft = await apiFetch('/email/draft', {
        method: 'POST',
        body: JSON.stringify({
          subject: subject || null,
          raw_body: raw,
          tone,
        }),
      }) as EmailDraft

      setSubject('')
      setRaw('')
      await loadThreads()
      await selectThread(draft.thread_id, draft.id)
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setBusy(false)
    }
  }

  async function refine() {
    if (!threadDetail || !activeDraftId) return
    const draft = threadDetail.drafts.find(d => d.id === activeDraftId)
    if (!draft) return

    const qList = safeParseList(draft.questions_to_ask)
    const qa = qList.map((question, index) => ({ question, answer: (answers[index] || '').trim() })).filter(item => item.answer)

    setRefining(true)
    setErr(null)
    try {
      const newDraft = await apiFetch('/email/refine', {
        method: 'POST',
        body: JSON.stringify({
          thread_id: threadDetail.id,
          draft_id: draft.id,
          tone,
          qa,
          note: note.trim() || null,
        }),
      }) as EmailDraft

      await loadThreads()
      await selectThread(threadDetail.id, newDraft.id)
    } catch (e: any) {
      setErr(e.message || String(e))
    } finally {
      setRefining(false)
    }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text)
  }

  const currentDraft = useMemo(() => {
    if (!threadDetail) return null
    return threadDetail.drafts.find(d => d.id === activeDraftId) || threadDetail.drafts[0] || null
  }, [threadDetail, activeDraftId])

  const compareDraft = useMemo(() => {
    if (!threadDetail || !compareDraftId) return null
    return threadDetail.drafts.find(d => d.id === compareDraftId) || null
  }, [threadDetail, compareDraftId])

  const compareOptions = useMemo(() => {
    if (!threadDetail) return []
    return threadDetail.drafts.filter(d => d.id !== activeDraftId)
  }, [threadDetail, activeDraftId])

  const flags = useMemo(() => safeParseList(currentDraft?.risk_flags || null), [currentDraft])
  const questions = useMemo(() => safeParseList(currentDraft?.questions_to_ask || null), [currentDraft])
  const rateCardText = rateCardDoc?.content?.trim() || ''
  const hasRateCard = Boolean(rateCardText)

  const canRefine = !!currentDraft && !!threadDetail && (questions.length === 0 || Object.values(answers).some(v => v.trim()) || note.trim().length > 0)
  const hasDealDraft = Boolean(threadDetail?.deal_draft)
  const isSponsoringIntent = threadDetail?.detected_intent === 'sponsoring'

  function insertRateCardIntoDraft() {
    if (!threadDetail || !activeDraftId || !rateCardText) return
    setThreadDetail(prev => {
      if (!prev) return prev
      const updatedDrafts = prev.drafts.map(d => {
        if (d.id !== activeDraftId) return d
        if ((d.draft_body || '').includes(rateCardText)) return d
        const base = d.draft_body && d.draft_body.trim().length > 0 ? `${d.draft_body}\n\n` : ''
        return {
          ...d,
          draft_body: `${base}${rateCardText}`,
        }
      })
      return { ...prev, drafts: updatedDrafts }
    })
  }

  function updateDealField(key: keyof Omit<DealDraftFormState, 'status'>, value: string) {
    setDealForm(prev => ({ ...prev, [key]: value }))
  }

  function updateDealStatus(value: DealDraftStatus) {
    setDealForm(prev => ({ ...prev, status: value }))
  }

  function buildDealPayload(form: DealDraftFormState) {
    const payload: Record<string, string | null> = {}
    dealFieldKeys.forEach(key => {
      const raw = form[key]
      const cleaned = typeof raw === 'string' ? raw.trim() : raw
      payload[key] = cleaned ? cleaned : null
    })
    return payload
  }

  async function autoFillDealDraft() {
    if (!threadDetail) return
    setDealAutoLoading(true)
    setDealErr(null)
    try {
      const data = await apiFetch('/deals/intake', {
        method: 'POST',
        body: JSON.stringify({ thread_id: threadDetail.id, auto_extract: true }),
      }) as DealDraft
      setThreadDetail(prev => (prev ? { ...prev, deal_draft: data } : prev))
      setDealForm(buildDealFormState(data))
    } catch (e: any) {
      setDealErr(e.message || String(e))
    } finally {
      setDealAutoLoading(false)
    }
  }

  async function saveDealDraft() {
    if (!threadDetail) return
    setDealSaving(true)
    setDealErr(null)
    const payload = buildDealPayload(dealForm)
    try {
      let data: DealDraft
      if (threadDetail.deal_draft) {
        data = await apiFetch(`/deals/${threadDetail.deal_draft.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ ...payload, status: dealForm.status }),
        }) as DealDraft
      } else {
        data = await apiFetch('/deals/intake', {
          method: 'POST',
          body: JSON.stringify({ thread_id: threadDetail.id, auto_extract: false, ...payload, status: dealForm.status }),
        }) as DealDraft
      }
      setThreadDetail(prev => (prev ? { ...prev, deal_draft: data } : prev))
      setDealForm(buildDealFormState(data))
    } catch (e: any) {
      setDealErr(e.message || String(e))
    } finally {
      setDealSaving(false)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">E-Mail Threads</h2>
          <div className="page-subtitle">Drafting, QA, Deal-Intake und Verlauf in einer Oberfläche.</div>
        </div>
        <button className="btn" onClick={loadThreads} disabled={threadsLoading}>
          {threadsLoading ? 'Aktualisiere…' : 'Refresh'}
        </button>
      </div>

      {err && <div className="error">{err}</div>}

      <div className="email-layout">
        <div className="card email-sidebar">
          <div className="section-head">
            <h3>Letzte Threads</h3>
            <span className="muted small">{threads.length} offen</span>
          </div>

          {threads.length === 0 && !threadsLoading && (
            <div className="muted small">Noch keine Threads.</div>
          )}

          <div className="stack">
            {threads.map(t => (
              <button
                key={t.id}
                className={`thread-pill ${t.id === selectedThreadId ? 'active' : ''}`}
                onClick={() => selectThread(t.id)}
              >
                <div className="row between">
                  <strong>{t.subject || '(ohne Betreff)'}</strong>
                  <span className="pill muted small">{t.detected_intent}</span>
                </div>
                <div className="muted small">{formatDate(t.updated_at)}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="email-main">
          <div className="card">
            <div className="control-row no-margin">
              <input
                className="grow"
                placeholder="Subject (optional)"
                value={subject}
                onChange={e => setSubject(e.target.value)}
              />
              <select value={tone} onChange={e => setTone(e.target.value as EmailTone)}>
                {toneOptions.map(opt => (
                  <option value={opt.value} key={opt.value}>{opt.label}</option>
                ))}
              </select>
              <button className="btn primary" onClick={generate} disabled={!raw.trim() || busy}>
                {busy ? '...' : 'Neuer Draft'}
              </button>
            </div>
            <textarea
              placeholder="E-Mail hier einfügen (raw)…"
              value={raw}
              onChange={e => setRaw(e.target.value)}
              rows={6}
            />
          </div>

          <div className="card email-thread-pane">
            {threadLoading && <div className="muted">Lade Thread…</div>}
            {!threadLoading && !threadDetail && (
              <div className="muted">Thread auswählen oder neuen Draft generieren.</div>
            )}

            {!threadLoading && threadDetail && (
              <div className="stack">
                <div className="section-head">
                  <div>
                    <h3>{threadDetail.subject || '(ohne Betreff)'}</h3>
                    <div className="muted small">Intent: {threadDetail.detected_intent}</div>
                    <div className="muted small">Aktualisiert: {formatDate(threadDetail.updated_at)}</div>
                  </div>
                </div>

                <div>
                  <div className="muted small">Original E-Mail</div>
                  <div className="prebox prebox-scroll">{threadDetail.raw_body}</div>
                </div>

                <div className="email-draft-layout">
                  <div className="card email-draft-main">
                    <div className="section-head">
                      <h3>Drafts</h3>
                      <div className="control-row">
                        {currentDraft && (
                          <button className="btn" onClick={() => copy(`${currentDraft.draft_subject || ''}\n\n${currentDraft.draft_body}`)}>
                            Copy
                          </button>
                        )}
                        <button
                          className="btn"
                          onClick={insertRateCardIntoDraft}
                          disabled={!hasRateCard || !currentDraft || rateCardLoading}
                        >
                          {rateCardLoading ? 'Lädt…' : 'Rate Card einfügen'}
                        </button>
                      </div>
                    </div>

                    {!hasRateCard && !rateCardLoading && (
                      <div className="muted small">
                        Rate Card fehlt · <Link to="/settings">hier hinterlegen</Link>
                      </div>
                    )}

                    {threadDetail.drafts.length === 0 && <div className="muted">Noch keine Drafts.</div>}

                    <div className="stack">
                      {threadDetail.drafts.map(d => (
                        <div
                          key={d.id}
                          className={`draft-card ${d.id === currentDraft?.id ? 'active' : ''}`}
                          onClick={() => setActiveDraftId(d.id)}
                        >
                          <div className="row between">
                            <strong>{d.draft_subject || '(leer)'}</strong>
                            <span className="muted small">{formatDate(d.created_at)}</span>
                          </div>
                          <div className="muted small">Tone: {d.tone}</div>
                          <p className="prebox draft-snippet">{d.draft_body}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="card email-checks">
                    <h3>Checks</h3>
                    <div className="muted small">Risk Flags</div>
                    <div className="control-row mt8">
                      {flags.length ? (
                        flags.map(flag => (
                          <span key={flag} className="pill">{flag}</span>
                        ))
                      ) : (
                        <span className="muted">Keine.</span>
                      )}
                    </div>

                    <hr />

                    <div className="muted small">Rückfragen</div>
                    <ul className="ul-tight">
                      {questions.length ? (
                        questions.map((q, i) => <li key={i}>{q}</li>)
                      ) : (
                        <li className="muted">Keine.</li>
                      )}
                    </ul>

                    {questions.length > 0 && (
                      <div className="stack section-gap">
                        {questions.map((q, i) => (
                          <div key={i}>
                            <div className="muted small">{q}</div>
                            <input
                              className="w100"
                              value={answers[i] || ''}
                              onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                              placeholder="Deine Antwort…"
                            />
                          </div>
                        ))}
                        <div>
                          <div className="muted small">Zusatz (optional)</div>
                          <textarea rows={3} value={note} onChange={e => setNote(e.target.value)} />
                        </div>
                        <button className="btn primary" onClick={refine} disabled={!canRefine || refining}>
                          {refining ? '...' : 'Refine'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="card">
                  <div className="section-head">
                    <div>
                      <h3>Deal Intake</h3>
                      <div className="muted small">
                        {hasDealDraft ? 'Deal Draft gespeichert' : 'Noch kein Deal Draft'} · Intent: {threadDetail.detected_intent}
                      </div>
                      {!isSponsoringIntent && (
                        <div className="muted small">Auto-Analyse liefert beste Ergebnisse bei Sponsoring-Mails.</div>
                      )}
                    </div>
                    <div className="control-row">
                      <button className="btn" onClick={autoFillDealDraft} disabled={dealAutoLoading || !threadDetail}>
                        {dealAutoLoading ? 'Analysiere…' : 'Auto aus Mail'}
                      </button>
                      <button className="btn primary" onClick={saveDealDraft} disabled={dealSaving || !threadDetail}>
                        {dealSaving ? 'Speichere…' : hasDealDraft ? 'Update' : 'Speichern'}
                      </button>
                    </div>
                  </div>

                  {dealErr && <div className="error small mt8">{dealErr}</div>}

                  <div className="deal-fields-grid section-gap">
                    <div className="stack">
                      <span className="muted small">Brand</span>
                      <input value={dealForm.brand_name} onChange={e => updateDealField('brand_name', e.target.value)} placeholder="Brand" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Kontakt</span>
                      <input value={dealForm.contact_name} onChange={e => updateDealField('contact_name', e.target.value)} placeholder="Name" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Kontakt E-Mail</span>
                      <input value={dealForm.contact_email} onChange={e => updateDealField('contact_email', e.target.value)} placeholder="brand@example.com" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Budget</span>
                      <input value={dealForm.budget} onChange={e => updateDealField('budget', e.target.value)} placeholder="z.B. 2.500 EUR" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Status</span>
                      <select value={dealForm.status} onChange={e => updateDealStatus(e.target.value as DealDraftStatus)}>
                        {dealStatusOptions.map(opt => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="deal-fields-grid-large section-gap">
                    <div className="stack">
                      <span className="muted small">Deliverables</span>
                      <textarea rows={3} value={dealForm.deliverables} onChange={e => updateDealField('deliverables', e.target.value)} placeholder="z.B. 1x YT Integration; 2x Stories" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Usage Rights</span>
                      <textarea rows={3} value={dealForm.usage_rights} onChange={e => updateDealField('usage_rights', e.target.value)} placeholder="Paid social 3 Monate; Newsletter" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Deadlines</span>
                      <textarea rows={3} value={dealForm.deadlines} onChange={e => updateDealField('deadlines', e.target.value)} placeholder="Briefing: 12.03; Publish: 28.03" />
                    </div>
                    <div className="stack">
                      <span className="muted small">Notes</span>
                      <textarea rows={3} value={dealForm.notes} onChange={e => updateDealField('notes', e.target.value)} placeholder="Zusätzliche Auflagen, Freigaben, etc." />
                    </div>
                  </div>
                </div>

                {currentDraft && compareOptions.length > 0 && (
                  <div className="card">
                    <div className="section-head">
                      <h3>Vergleich</h3>
                      <select
                        value={compareDraftId || ''}
                        onChange={e => setCompareDraftId(e.target.value || null)}
                      >
                        {compareOptions.map(opt => (
                          <option value={opt.id} key={opt.id}>
                            {formatDate(opt.created_at)} · {opt.tone}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="comparison-grid">
                      <div className="comparison-column">
                        <div className="comparison-header">
                          <strong>Vorher</strong>
                          <span className="muted small">{compareDraft ? formatDate(compareDraft.created_at) : ''}</span>
                        </div>
                        {compareDraft ? (
                          <>
                            <div className="muted small">Subject</div>
                            <div className="prebox comparison-pre">{compareDraft.draft_subject || '(leer)'}</div>
                            <div className="muted small">Body</div>
                            <div className="prebox comparison-pre">{compareDraft.draft_body}</div>
                          </>
                        ) : (
                          <div className="muted">Wähle einen Draft zum Vergleich.</div>
                        )}
                      </div>

                      <div className="comparison-column">
                        <div className="comparison-header">
                          <strong>Neu</strong>
                          <span className="muted small">{formatDate(currentDraft.created_at)}</span>
                        </div>
                        <div className="muted small">Subject</div>
                        <div className="prebox comparison-pre">{currentDraft.draft_subject || '(leer)'}</div>
                        <div className="muted small">Body</div>
                        <div className="prebox comparison-pre">{currentDraft.draft_body}</div>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <h3>Verlauf</h3>
                  <div className="stack">
                    {threadDetail.messages.length === 0 && <div className="muted">Noch kein Verlauf.</div>}
                    {threadDetail.messages.map(msg => (
                      <div key={msg.id} className={`message-pill ${msg.role}`}>
                        <div className="row between">
                          <span className="muted small">{msg.role} · {formatDate(msg.created_at)}</span>
                          {msg.payload?.action && (
                            <span className="pill muted small">{msg.payload.action}</span>
                          )}
                        </div>
                        <div className="prebox">
                          {msg.content || JSON.stringify(msg.payload, null, 2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
