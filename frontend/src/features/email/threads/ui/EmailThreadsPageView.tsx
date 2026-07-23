import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../../../api'
import { useAuthz } from '../../../../shared/hooks/useAuthz'
import { useDebouncedValue } from '../../../../shared/hooks/useDebouncedValue'
import { useRateCardDoc } from '../../../../shared/hooks/useRateCardDoc'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { useI18n } from '../../../../shared/i18n/i18n'

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
  parent_draft_id: string | null
  template_id: string | null
  version_number: number
  source: 'ai_generate' | 'ai_refine' | 'template' | 'manual'
  tone: EmailTone
  draft_subject: string | null
  draft_body: string
  questions_to_ask: string | null
  risk_flags: string | null
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  risk_summary: string | null
  approval_required: boolean
  approval_status: 'not_required' | 'pending' | 'approved' | 'rejected'
  approved: boolean
  approval_reason: string | null
  handoff_status: 'draft' | 'blocked' | 'ready_for_send' | 'handed_off'
  handoff_note: string | null
  handed_off_by_name: string | null
  handed_off_at: string | null
  created_at: string
  updated_at: string
}

type EmailKnowledgeEvidence = {
  draft_id: string
  knowledge_doc_id: string
  knowledge_doc_title: string
  knowledge_doc_type: string
  linked_at: string
  linked_by_name: string | null
}

type EmailTemplate = {
  id: string
  thread_id: string | null
  name: string
  intent: string
  subject_template: string | null
  body_template: string
  active: boolean
  created_by_name: string | null
  created_at: string
  updated_at: string
}

type EmailDraftVersion = {
  id: string
  draft_id: string
  version_number: number
  draft_subject: string | null
  draft_body: string
  tone: EmailTone
  changed_by_name: string | null
  change_reason: string | null
  created_at: string
}

type EmailDraftSuggestion = {
  id: string
  draft_id: string
  suggestion_type: string
  source: string
  summary: string | null
  payload: Record<string, unknown> | null
  decided: boolean
  decided_by_name: string | null
  decided_at: string | null
  created_at: string
}

type EmailThreadMessage = {
  id: string
  thread_id: string
  role: 'user' | 'assistant' | 'system'
  content: string | null
  payload?: Record<string, unknown> | null
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
  templates: EmailTemplate[]
  draft_versions: EmailDraftVersion[]
  draft_suggestions: EmailDraftSuggestion[]
  knowledge_evidence: EmailKnowledgeEvidence[]
  deal_draft: DealDraft | null
}

type CreatorAiProfile = {
  id: string
  owner_user_id: string | null
  profile_name: string
  is_global_default: boolean
  is_active: boolean
  clear_name: string
  artist_name: string
  channel_link: string
  themes: string[]
  platforms: string[]
  short_description: string | null
  tone: 'neutral' | 'friendly' | 'professional' | 'energetic' | 'direct'
  target_audience: string | null
  language_code: string
  content_focus: string[]
}

type CreatorAiSettingsPreview = {
  source: string
  profile_id: string | null
  profile_name: string | null
  missing_required: string[]
  applied_settings: {
    clear_name: string | null
    artist_name: string | null
    channel_link: string | null
    themes: string[]
    platforms: string[]
    short_description: string
    tone: string | null
    target_audience: string
    language_code: string | null
    content_focus: string[]
  }
}

type AnswersState = Record<number, string>

type ThreadsResponse =
  | EmailThreadSummary[]
  | {
      items?: EmailThreadSummary[]
    }

function getThreadsItems(input: ThreadsResponse): EmailThreadSummary[] {
  return Array.isArray(input) ? input : (input.items ?? [])
}

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
  } catch {
    return value
  }
}

function safeParseList(value: string | null): string[] {
  if (!value) return []
  try {
    const arr = JSON.parse(value)
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

export default function EmailPage() {
  const { hasPermission, me } = useAuthz()
  const { language } = useI18n()
  const [subject, setSubject] = useState('')
  const [raw, setRaw] = useState('')
  const [tone, setTone] = useState<EmailTone>('neutral')

  const [threads, setThreads] = useState<EmailThreadSummary[]>([])
  const [threadsLoading, setThreadsLoading] = useState(false)
  const threadsRequestRef = useRef(0)
  const [threadSearchInput, setThreadSearchInput] = useState('')
  const [threadsPageSize, setThreadsPageSize] = useState(20)
  const [threadsOffset, setThreadsOffset] = useState(0)
  const debouncedThreadSearch = useDebouncedValue(threadSearchInput.trim().toLowerCase(), 250)

  const [selectedThreadId, setSelectedThreadId] = useState<string | null>(null)
  const [threadDetail, setThreadDetail] = useState<EmailThreadDetail | null>(null)
  const [threadLoading, setThreadLoading] = useState(false)
  const threadDetailRequestRef = useRef(0)
  const [activeDraftId, setActiveDraftId] = useState<string | null>(null)
  const [compareDraftId, setCompareDraftId] = useState<string | null>(null)

  const [answers, setAnswers] = useState<AnswersState>({})
  const [note, setNote] = useState('')
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('')
  const [approvalReason, setApprovalReason] = useState('')
  const [handoffNote, setHandoffNote] = useState('')
  const [templateName, setTemplateName] = useState('')
  const [templateSubject, setTemplateSubject] = useState('')
  const [templateBody, setTemplateBody] = useState('')
  const [templateSaving, setTemplateSaving] = useState(false)
  const [draftSubjectEdit, setDraftSubjectEdit] = useState('')
  const [draftBodyEdit, setDraftBodyEdit] = useState('')
  const [draftEditReason, setDraftEditReason] = useState('')
  const [draftSaving, setDraftSaving] = useState(false)

  const [creatorProfiles, setCreatorProfiles] = useState<CreatorAiProfile[]>([])
  const [selectedCreatorProfileId, setSelectedCreatorProfileId] = useState('')
  const [settingsPreview, setSettingsPreview] = useState<CreatorAiSettingsPreview | null>(null)
  const [profilesLoading, setProfilesLoading] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)

  const [profileName, setProfileName] = useState('')
  const [profileClearName, setProfileClearName] = useState('')
  const [profileArtistName, setProfileArtistName] = useState('')
  const [profileChannelLink, setProfileChannelLink] = useState('')
  const [profileThemesCsv, setProfileThemesCsv] = useState('')
  const [profilePlatformsCsv, setProfilePlatformsCsv] = useState('youtube')
  const [profileShortDescription, setProfileShortDescription] = useState('')
  const [profileTone, setProfileTone] = useState<
    'neutral' | 'friendly' | 'professional' | 'energetic' | 'direct'
  >('neutral')
  const [profileTargetAudience, setProfileTargetAudience] = useState('')
  const [profileLanguageCode, setProfileLanguageCode] = useState('de')
  const [profileContentFocusCsv, setProfileContentFocusCsv] = useState('community')

  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [refining, setRefining] = useState(false)
  const { doc: rateCardDoc, loading: rateCardLoading } = useRateCardDoc()
  const [dealForm, setDealForm] = useState<DealDraftFormState>(() => buildDealFormState(null))
  const [dealSaving, setDealSaving] = useState(false)
  const [dealAutoLoading, setDealAutoLoading] = useState(false)
  const [dealErr, setDealErr] = useState<string | null>(null)
  const dealDraftRef = useRef(threadDetail?.deal_draft ?? null)
  dealDraftRef.current = threadDetail?.deal_draft ?? null
  const loadThreadsRef = useRef(loadThreads)
  loadThreadsRef.current = loadThreads
  const loadCreatorProfilesRef = useRef(loadCreatorProfiles)
  loadCreatorProfilesRef.current = loadCreatorProfiles

  useEffect(() => {
    void loadThreadsRef.current()
  }, [threadsPageSize, threadsOffset])

  useEffect(() => {
    if (!hasPermission('email.generate')) return
    void loadCreatorProfilesRef.current()
  }, [hasPermission])

  useEffect(() => {
    if (!hasPermission('email.generate')) return
    void loadSettingsPreview(selectedCreatorProfileId || null)
  }, [selectedCreatorProfileId, hasPermission])

  useEffect(() => {
    setAnswers({})
    setNote('')
  }, [activeDraftId])

  useEffect(() => {
    const draft = threadDetail?.drafts.find((item) => item.id === activeDraftId) || null
    setDraftSubjectEdit(draft?.draft_subject || '')
    setDraftBodyEdit(draft?.draft_body || '')
    setDraftEditReason('')
  }, [activeDraftId, threadDetail])

  useEffect(() => {
    setDealForm(buildDealFormState(dealDraftRef.current))
    setDealErr(null)
  }, [threadDetail?.deal_draft?.id, threadDetail?.id])

  async function loadThreads() {
    const requestId = threadsRequestRef.current + 1
    threadsRequestRef.current = requestId
    setThreadsLoading(true)
    try {
      const data = (await apiFetch(
        `/email/threads?limit=${threadsPageSize}&offset=${threadsOffset}&sort_by=updated_at&sort_order=desc`
      )) as ThreadsResponse
      if (requestId !== threadsRequestRef.current) return
      const items = getThreadsItems(data)
      setThreads(items)
      if (selectedThreadId && items.some((thread) => thread.id === selectedThreadId)) {
        return
      }
      if (items.length) {
        await selectThread(items[0].id)
      }
    } catch (e: unknown) {
      if (requestId !== threadsRequestRef.current) return
      setErr(getErrorMessage(e))
    } finally {
      if (requestId === threadsRequestRef.current) {
        setThreadsLoading(false)
      }
    }
  }

  function csvToList(value: string): string[] {
    return value
      .split(',')
      .map((entry) => entry.trim())
      .filter(Boolean)
  }

  function applyProfileToForm(profile: CreatorAiProfile) {
    setProfileName(profile.profile_name)
    setProfileClearName(profile.clear_name)
    setProfileArtistName(profile.artist_name)
    setProfileChannelLink(profile.channel_link)
    setProfileThemesCsv((profile.themes || []).join(', '))
    setProfilePlatformsCsv((profile.platforms || []).join(', '))
    setProfileShortDescription(profile.short_description || '')
    setProfileTone(profile.tone)
    setProfileTargetAudience(profile.target_audience || '')
    setProfileLanguageCode(profile.language_code || 'de')
    setProfileContentFocusCsv((profile.content_focus || []).join(', '))
  }

  async function loadCreatorProfiles() {
    setProfilesLoading(true)
    try {
      const data = (await apiFetch(
        '/email/ai-settings/profiles?include_global_default=true'
      )) as CreatorAiProfile[]
      setCreatorProfiles(data)
      if (!selectedCreatorProfileId) {
        const firstUserProfile = data.find((profile) => !profile.is_global_default) || data[0]
        if (firstUserProfile) {
          setSelectedCreatorProfileId(firstUserProfile.id)
          applyProfileToForm(firstUserProfile)
        }
      }
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setProfilesLoading(false)
    }
  }

  async function loadSettingsPreview(profileId: string | null) {
    try {
      const query = profileId ? `?profile_id=${encodeURIComponent(profileId)}` : ''
      const preview = (await apiFetch(
        `/email/ai-settings/preview${query}`
      )) as CreatorAiSettingsPreview
      setSettingsPreview(preview)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  async function saveCreatorProfile() {
    if (!canGenerate) return
    const payload = {
      profile_name: profileName.trim() || 'Creator Profil',
      is_active: true,
      clear_name: profileClearName.trim(),
      artist_name: profileArtistName.trim(),
      channel_link: profileChannelLink.trim(),
      themes: csvToList(profileThemesCsv),
      platforms: csvToList(profilePlatformsCsv),
      short_description: profileShortDescription.trim() || null,
      tone: profileTone,
      target_audience: profileTargetAudience.trim() || null,
      language_code: profileLanguageCode.trim() || 'de',
      content_focus: csvToList(profileContentFocusCsv),
    }

    setSettingsSaving(true)
    setErr(null)
    let previewProfileId = selectedCreatorProfileId || null
    try {
      if (selectedCreatorProfileId) {
        const existing = creatorProfiles.find((profile) => profile.id === selectedCreatorProfileId)
        if (existing?.is_global_default && me?.role === 'admin') {
          await apiFetch('/email/ai-settings/default', {
            method: 'PUT',
            body: JSON.stringify(payload),
          })
        } else {
          await apiFetch(`/email/ai-settings/profiles/${selectedCreatorProfileId}`, {
            method: 'PATCH',
            body: JSON.stringify(payload),
          })
        }
      } else {
        const created = (await apiFetch('/email/ai-settings/profiles', {
          method: 'POST',
          body: JSON.stringify(payload),
        })) as CreatorAiProfile
        setSelectedCreatorProfileId(created.id)
        previewProfileId = created.id
      }

      await loadCreatorProfiles()
      await loadSettingsPreview(previewProfileId)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setSettingsSaving(false)
    }
  }

  async function selectThread(id: string, focusDraftId?: string) {
    setSelectedThreadId(id)
    setCompareDraftId(null)
    await loadThreadDetail(id, focusDraftId)
  }

  async function loadThreadDetail(id: string, focusDraftId?: string) {
    const requestId = threadDetailRequestRef.current + 1
    threadDetailRequestRef.current = requestId
    setThreadLoading(true)
    try {
      const detail = (await apiFetch(`/email/threads/${id}`)) as EmailThreadDetail
      if (requestId !== threadDetailRequestRef.current) return
      setThreadDetail(detail)
      const fallback = detail.drafts.length ? detail.drafts[0].id : null
      setActiveDraftId(focusDraftId || fallback)
    } catch (e: unknown) {
      if (requestId !== threadDetailRequestRef.current) return
      setErr(getErrorMessage(e))
    } finally {
      if (requestId === threadDetailRequestRef.current) {
        setThreadLoading(false)
      }
    }
  }

  useEffect(() => {
    if (!threadDetail || !activeDraftId) {
      setCompareDraftId(null)
      return
    }
    const drafts = threadDetail.drafts
    const activeIdx = drafts.findIndex((d) => d.id === activeDraftId)
    if (activeIdx === -1) {
      setCompareDraftId(null)
      return
    }
    const fallback = drafts[activeIdx + 1] || drafts.find((d) => d.id !== activeDraftId)
    if (!fallback) {
      setCompareDraftId(null)
      return
    }
    if (
      !compareDraftId ||
      compareDraftId === activeDraftId ||
      !drafts.some((d) => d.id === compareDraftId)
    ) {
      setCompareDraftId(fallback.id)
    }
  }, [threadDetail, activeDraftId, compareDraftId])

  async function generate() {
    if (!hasPermission('email.generate')) return
    if (!raw.trim()) return
    setBusy(true)
    setErr(null)
    try {
      const draft = (await apiFetch('/email/draft', {
        method: 'POST',
        body: JSON.stringify({
          subject: subject || null,
          raw_body: raw,
          tone,
          template_id: selectedTemplateId || null,
          creator_profile_id: selectedCreatorProfileId || null,
        }),
      })) as EmailDraft

      setSubject('')
      setRaw('')
      await loadThreads()
      await selectThread(draft.thread_id, draft.id)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  async function refine() {
    if (!hasPermission('email.generate')) return
    if (!threadDetail || !activeDraftId) return
    const draft = threadDetail.drafts.find((d) => d.id === activeDraftId)
    if (!draft) return

    const qList = safeParseList(draft.questions_to_ask)
    const qa = qList
      .map((question, index) => ({ question, answer: (answers[index] || '').trim() }))
      .filter((item) => item.answer)

    setRefining(true)
    setErr(null)
    try {
      const newDraft = (await apiFetch('/email/refine', {
        method: 'POST',
        body: JSON.stringify({
          thread_id: threadDetail.id,
          draft_id: draft.id,
          tone,
          template_id: selectedTemplateId || null,
          creator_profile_id: selectedCreatorProfileId || null,
          qa,
          note: note.trim() || null,
        }),
      })) as EmailDraft

      await loadThreads()
      await selectThread(threadDetail.id, newDraft.id)
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setRefining(false)
    }
  }

  function copy(text: string) {
    navigator.clipboard.writeText(text)
  }

  async function setApproval(approved: boolean) {
    if (!currentDraft) return
    setErr(null)
    try {
      await apiFetch(`/email/drafts/${currentDraft.id}/approval`, {
        method: 'PATCH',
        body: JSON.stringify({ approved, reason: approvalReason.trim() || null }),
      })
      if (threadDetail) await loadThreadDetail(threadDetail.id, currentDraft.id)
      setApprovalReason('')
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  async function setHandoff(status: 'draft' | 'blocked' | 'ready_for_send' | 'handed_off') {
    if (!currentDraft) return
    setErr(null)
    try {
      await apiFetch(`/email/drafts/${currentDraft.id}/handoff`, {
        method: 'PATCH',
        body: JSON.stringify({ status, note: handoffNote.trim() || null }),
      })
      if (threadDetail) await loadThreadDetail(threadDetail.id, currentDraft.id)
      if (status === 'handed_off' || status === 'blocked') setHandoffNote('')
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    }
  }

  async function saveTemplate() {
    if (!threadDetail) return
    const cleanedName = templateName.trim()
    const cleanedBody = templateBody.trim()
    if (!cleanedName || !cleanedBody) return
    setTemplateSaving(true)
    setErr(null)
    try {
      await apiFetch('/email/templates', {
        method: 'POST',
        body: JSON.stringify({
          name: cleanedName,
          intent: threadDetail.detected_intent || 'unknown',
          subject_template: templateSubject.trim() || null,
          body_template: cleanedBody,
          thread_id: threadDetail.id,
          active: true,
        }),
      })
      await loadThreadDetail(threadDetail.id, currentDraft?.id)
      setTemplateName('')
      setTemplateSubject('')
      setTemplateBody('')
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setTemplateSaving(false)
    }
  }

  async function saveDraftEdits() {
    if (!currentDraft || !threadDetail) return
    setDraftSaving(true)
    setErr(null)
    try {
      await apiFetch(`/email/drafts/${currentDraft.id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          draft_subject: draftSubjectEdit.trim() || null,
          draft_body: draftBodyEdit.trim(),
          change_reason: draftEditReason.trim() || null,
        }),
      })
      await loadThreadDetail(threadDetail.id, currentDraft.id)
      setDraftEditReason('')
    } catch (e: unknown) {
      setErr(getErrorMessage(e))
    } finally {
      setDraftSaving(false)
    }
  }

  const currentDraft = useMemo(() => {
    if (!threadDetail) return null
    return threadDetail.drafts.find((d) => d.id === activeDraftId) || threadDetail.drafts[0] || null
  }, [threadDetail, activeDraftId])

  const compareDraft = useMemo(() => {
    if (!threadDetail || !compareDraftId) return null
    return threadDetail.drafts.find((d) => d.id === compareDraftId) || null
  }, [threadDetail, compareDraftId])

  const compareOptions = useMemo(() => {
    if (!threadDetail) return []
    return threadDetail.drafts.filter((d) => d.id !== activeDraftId)
  }, [threadDetail, activeDraftId])

  const versionsForCurrentDraft = useMemo(() => {
    if (!threadDetail || !currentDraft) return []
    return threadDetail.draft_versions.filter((version) => version.draft_id === currentDraft.id)
  }, [threadDetail, currentDraft])

  const suggestionsForCurrentDraft = useMemo(() => {
    if (!threadDetail || !currentDraft) return []
    return threadDetail.draft_suggestions.filter(
      (suggestion) => suggestion.draft_id === currentDraft.id
    )
  }, [threadDetail, currentDraft])

  const knowledgeEvidenceForCurrentDraft = useMemo(() => {
    if (!threadDetail || !currentDraft) return []
    return threadDetail.knowledge_evidence.filter((entry) => entry.draft_id === currentDraft.id)
  }, [threadDetail, currentDraft])

  const flags = useMemo(() => safeParseList(currentDraft?.risk_flags || null), [currentDraft])
  const questions = useMemo(
    () => safeParseList(currentDraft?.questions_to_ask || null),
    [currentDraft]
  )

  const confidenceIndicator = useMemo(() => {
    if (!currentDraft) return { score: 0, label: 'n/a', tone: 'warn' as const }
    let score = 100
    if (currentDraft.risk_level === 'medium') score -= 20
    if (currentDraft.risk_level === 'high') score -= 40
    if (currentDraft.risk_level === 'critical') score -= 60
    score -= Math.min(flags.length * 5, 25)
    if (currentDraft.approval_status !== 'approved') score -= 10
    if (currentDraft.handoff_status === 'blocked') score -= 10
    const bounded = Math.max(0, Math.min(100, score))
    if (bounded >= 75) return { score: bounded, label: 'high', tone: 'info' as const }
    if (bounded >= 50) return { score: bounded, label: 'medium', tone: 'warn' as const }
    return { score: bounded, label: 'low', tone: 'danger' as const }
  }, [currentDraft, flags.length])

  const visibleThreads = useMemo(() => {
    if (!debouncedThreadSearch) return threads
    return threads.filter((thread) => {
      const subject = (thread.subject || '').toLowerCase()
      const intent = thread.detected_intent.toLowerCase()
      const body = (thread.raw_body || '').toLowerCase()
      return (
        subject.includes(debouncedThreadSearch) ||
        intent.includes(debouncedThreadSearch) ||
        body.includes(debouncedThreadSearch)
      )
    })
  }, [threads, debouncedThreadSearch])

  const rateCardText = rateCardDoc?.content?.trim() || ''
  const hasRateCard = Boolean(rateCardText)

  const canGenerate = hasPermission('email.generate')
  const canManageDeals = hasPermission('deal.manage')
  const canRefine =
    canGenerate &&
    !!currentDraft &&
    !!threadDetail &&
    (questions.length === 0 ||
      Object.values(answers).some((v) => v.trim()) ||
      note.trim().length > 0)
  const hasDealDraft = Boolean(threadDetail?.deal_draft)
  const isSponsoringIntent = threadDetail?.detected_intent === 'sponsoring'

  function insertRateCardIntoDraft() {
    if (!threadDetail || !activeDraftId || !rateCardText) return
    setThreadDetail((prev) => {
      if (!prev) return prev
      const updatedDrafts = prev.drafts.map((d) => {
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
    setDealForm((prev) => ({ ...prev, [key]: value }))
  }

  function updateDealStatus(value: DealDraftStatus) {
    setDealForm((prev) => ({ ...prev, status: value }))
  }

  function buildDealPayload(form: DealDraftFormState) {
    const payload: Record<string, string | null> = {}
    dealFieldKeys.forEach((key) => {
      const raw = form[key]
      const cleaned = typeof raw === 'string' ? raw.trim() : raw
      payload[key] = cleaned ? cleaned : null
    })
    return payload
  }

  async function autoFillDealDraft() {
    if (!hasPermission('deal.manage')) return
    if (!threadDetail) return
    setDealAutoLoading(true)
    setDealErr(null)
    try {
      const data = (await apiFetch('/deals/intake', {
        method: 'POST',
        body: JSON.stringify({ thread_id: threadDetail.id, auto_extract: true }),
      })) as DealDraft
      setThreadDetail((prev) => (prev ? { ...prev, deal_draft: data } : prev))
      setDealForm(buildDealFormState(data))
    } catch (e: unknown) {
      setDealErr(getErrorMessage(e))
    } finally {
      setDealAutoLoading(false)
    }
  }

  async function saveDealDraft() {
    if (!hasPermission('deal.manage')) return
    if (!threadDetail) return
    setDealSaving(true)
    setDealErr(null)
    const payload = buildDealPayload(dealForm)
    try {
      let data: DealDraft
      if (threadDetail.deal_draft) {
        data = (await apiFetch(`/deals/${threadDetail.deal_draft.id}`, {
          method: 'PATCH',
          body: JSON.stringify({ ...payload, status: dealForm.status }),
        })) as DealDraft
      } else {
        data = (await apiFetch('/deals/intake', {
          method: 'POST',
          body: JSON.stringify({
            thread_id: threadDetail.id,
            auto_extract: false,
            ...payload,
            status: dealForm.status,
          }),
        })) as DealDraft
      }
      setThreadDetail((prev) => (prev ? { ...prev, deal_draft: data } : prev))
      setDealForm(buildDealFormState(data))
    } catch (e: unknown) {
      setDealErr(getErrorMessage(e))
    } finally {
      setDealSaving(false)
    }
  }

  return (
    <div className="container">
      <div className="page-header">
        <div>
          <h2 className="page-title">{language === 'en' ? 'Email threads' : 'E-Mail Threads'}</h2>
          <div className="page-subtitle">
            {language === 'en'
              ? 'Drafting, QA, deal intake and history in one workspace.'
              : 'Drafting, QA, Deal-Intake und Verlauf in einer Oberfläche.'}
          </div>
          <div className="muted small">
            {language === 'en'
              ? 'AI only creates suggestions. Sending is never automatic and requires human approval.'
              : 'AI erstellt nur Vorschläge. Versand erfolgt nie automatisch und erfordert menschliche Freigabe.'}
          </div>
        </div>
        <button className="btn" onClick={loadThreads} disabled={threadsLoading}>
          {threadsLoading
            ? language === 'en'
              ? 'Refreshing…'
              : 'Aktualisiere…'
            : language === 'en'
              ? 'Refresh'
              : 'Aktualisieren'}
        </button>
      </div>

      {err && (
        <div className="error" role="alert">
          {err}
        </div>
      )}

      <div className="email-layout">
        <div className="card email-sidebar">
          <div className="section-head">
            <h3>{language === 'en' ? 'Recent threads' : 'Letzte Threads'}</h3>
            <span className="muted small">
              {visibleThreads.length} {language === 'en' ? 'visible' : 'sichtbar'}
            </span>
          </div>

          <div className="control-row section-gap">
            <input
              className="grow"
              placeholder={language === 'en' ? 'Search threads…' : 'Threads suchen…'}
              value={threadSearchInput}
              onChange={(event) => setThreadSearchInput(event.target.value)}
            />
            <select
              value={String(threadsPageSize)}
              onChange={(event) => {
                setThreadsPageSize(Number(event.target.value))
                setThreadsOffset(0)
              }}
            >
              <option value="20">20 {language === 'en' ? '/ page' : '/ Seite'}</option>
              <option value="40">40 {language === 'en' ? '/ page' : '/ Seite'}</option>
            </select>
          </div>

          {visibleThreads.length === 0 && !threadsLoading && (
            <div className="muted small">
              {language === 'en' ? 'No threads yet.' : 'Noch keine Threads.'}
            </div>
          )}

          <div className="stack">
            {visibleThreads.map((t) => (
              <button
                key={t.id}
                className={`thread-pill ${t.id === selectedThreadId ? 'active' : ''}`}
                onClick={() => selectThread(t.id)}
              >
                <div className="row between">
                  <strong>
                    {t.subject || (language === 'en' ? '(no subject)' : '(ohne Betreff)')}
                  </strong>
                  <span className="pill muted small">{t.detected_intent}</span>
                </div>
                <div className="muted small">{formatDate(t.updated_at)}</div>
              </button>
            ))}
          </div>
          <div className="row between mt8">
            <button
              className="btn"
              onClick={() => setThreadsOffset((current) => Math.max(0, current - threadsPageSize))}
              disabled={threadsOffset <= 0}
            >
              {language === 'en' ? '← Back' : '← Zurück'}
            </button>
            <span className="muted small">
              {language === 'en' ? 'Offset' : 'Offset'} {threadsOffset} ·{' '}
              {language === 'en' ? 'Limit' : 'Limit'} {threadsPageSize}
            </span>
            <button
              className="btn"
              onClick={() => setThreadsOffset((current) => current + threadsPageSize)}
              disabled={threads.length < threadsPageSize}
            >
              {language === 'en' ? 'Next →' : 'Weiter →'}
            </button>
          </div>
        </div>

        <div className="email-main">
          <div className="card">
            <div className="control-row no-margin">
              <label className="sr-only" htmlFor="email-thread-subject">
                {language === 'en' ? 'Subject' : 'Betreff'}
              </label>
              <input
                id="email-thread-subject"
                className="grow"
                placeholder="Subject (optional)"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
              />
              <label className="sr-only" htmlFor="email-thread-tone">
                Tonfall
              </label>
              <select
                id="email-thread-tone"
                value={tone}
                onChange={(e) => setTone(e.target.value as EmailTone)}
              >
                {toneOptions.map((opt) => (
                  <option value={opt.value} key={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <label className="sr-only" htmlFor="email-thread-template">
                Template
              </label>
              <select
                id="email-thread-template"
                value={selectedTemplateId}
                onChange={(event) => setSelectedTemplateId(event.target.value)}
              >
                <option value="">{language === 'en' ? 'No template' : 'Kein Template'}</option>
                {(threadDetail?.templates || []).map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.name}
                  </option>
                ))}
              </select>
              <label className="sr-only" htmlFor="email-creator-profile">
                {language === 'en' ? 'Creator profile' : 'Creator Profil'}
              </label>
              <select
                id="email-creator-profile"
                value={selectedCreatorProfileId}
                onChange={(event) => {
                  const profileId = event.target.value
                  setSelectedCreatorProfileId(profileId)
                  const profile = creatorProfiles.find((item) => item.id === profileId)
                  if (profile) applyProfileToForm(profile)
                }}
                disabled={profilesLoading}
              >
                <option value="">
                  {language === 'en'
                    ? 'Auto / configured default'
                    : 'Auto / konfigurierter Default'}
                </option>
                {creatorProfiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.is_global_default
                      ? `[Global] ${profile.profile_name}`
                      : profile.profile_name}
                  </option>
                ))}
              </select>
              <button
                className="btn primary"
                onClick={generate}
                disabled={!canGenerate || !raw.trim() || busy}
              >
                {busy ? '...' : language === 'en' ? 'New draft' : 'Neuer Draft'}
              </button>
            </div>
            <textarea
              aria-label={language === 'en' ? 'Email raw text' : 'E-Mail Rohtext'}
              placeholder={
                language === 'en' ? 'Paste email here (raw)…' : 'E-Mail hier einfügen (raw)…'
              }
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              rows={6}
            />
          </div>

          <div className="card email-thread-pane">
            {threadLoading && (
              <div className="muted" role="status" aria-live="polite">
                {language === 'en' ? 'Loading thread…' : 'Lade Thread…'}
              </div>
            )}
            {!threadLoading && !threadDetail && (
              <div className="muted">
                {language === 'en'
                  ? 'Select a thread or generate a new draft.'
                  : 'Thread auswählen oder neuen Draft generieren.'}
              </div>
            )}

            {!threadLoading && threadDetail && (
              <div className="stack">
                <div className="section-head">
                  <div>
                    <h3>
                      {threadDetail.subject ||
                        (language === 'en' ? '(no subject)' : '(ohne Betreff)')}
                    </h3>
                    <div className="muted small">Intent: {threadDetail.detected_intent}</div>
                    <div className="muted small">
                      {language === 'en' ? 'Updated' : 'Aktualisiert'}:{' '}
                      {formatDate(threadDetail.updated_at)}
                    </div>
                  </div>
                </div>

                <div>
                  <div className="muted small">
                    {language === 'en' ? 'Original email' : 'Original E-Mail'}
                  </div>
                  <div className="prebox prebox-scroll">{threadDetail.raw_body}</div>
                </div>

                <div className="email-draft-layout">
                  <div className="card email-draft-main">
                    <div className="section-head">
                      <h3>Drafts</h3>
                      <div className="control-row">
                        {currentDraft && (
                          <button
                            className="btn"
                            onClick={() =>
                              copy(
                                `${currentDraft.draft_subject || ''}\n\n${currentDraft.draft_body}`
                              )
                            }
                          >
                            Copy
                          </button>
                        )}
                        <button
                          className="btn"
                          onClick={insertRateCardIntoDraft}
                          disabled={!hasRateCard || !currentDraft || rateCardLoading}
                        >
                          {rateCardLoading
                            ? language === 'en'
                              ? 'Loading…'
                              : 'Lädt…'
                            : language === 'en'
                              ? 'Insert rate card'
                              : 'Rate Card einfügen'}
                        </button>
                      </div>
                    </div>

                    {!hasRateCard && !rateCardLoading && (
                      <div className="muted small">
                        Rate Card fehlt · <Link to="/settings">hier hinterlegen</Link>
                      </div>
                    )}

                    {threadDetail.drafts.length === 0 && (
                      <div className="muted">
                        {language === 'en' ? 'No drafts yet.' : 'Noch keine Drafts.'}
                      </div>
                    )}

                    <div className="stack">
                      {threadDetail.drafts.map((d) => (
                        <div
                          key={d.id}
                          className={`draft-card ${d.id === currentDraft?.id ? 'active' : ''}`}
                          onClick={() => setActiveDraftId(d.id)}
                          role="button"
                          tabIndex={0}
                          aria-pressed={d.id === currentDraft?.id}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault()
                              setActiveDraftId(d.id)
                            }
                          }}
                        >
                          <div className="row between">
                            <strong>
                              {d.draft_subject || (language === 'en' ? '(empty)' : '(leer)')}
                            </strong>
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
                        flags.map((flag) => (
                          <span key={flag} className="pill">
                            {flag}
                          </span>
                        ))
                      ) : (
                        <span className="muted">{language === 'en' ? 'None.' : 'Keine.'}</span>
                      )}
                    </div>

                    {currentDraft && (
                      <div className="stack mt8">
                        <div className="muted small">
                          Risk Level: <strong>{currentDraft.risk_level}</strong>
                        </div>
                        <div className="muted small">
                          Summary:{' '}
                          {currentDraft.risk_summary ||
                            (language === 'en' ? 'No details' : 'Keine Details')}
                        </div>
                        <div className="muted small">Approval: {currentDraft.approval_status}</div>
                        <div className="muted small">Handoff: {currentDraft.handoff_status}</div>
                        <div className="muted small">
                          Confidence:{' '}
                          <strong>
                            {confidenceIndicator.score}% ({confidenceIndicator.label})
                          </strong>
                        </div>
                      </div>
                    )}

                    <hr />

                    {currentDraft && (
                      <div className="stack section-gap">
                        <div className="muted small">
                          {language === 'en' ? 'Approval / handoff' : 'Freigabe / Handoff'}
                        </div>
                        <input
                          className="w100"
                          value={approvalReason}
                          onChange={(event) => setApprovalReason(event.target.value)}
                          placeholder={
                            language === 'en'
                              ? 'Approval or rejection reason'
                              : 'Freigabe- oder Ablehnungsgrund'
                          }
                        />
                        <div className="control-row">
                          <button
                            className="btn"
                            onClick={() => setApproval(true)}
                            disabled={!canGenerate}
                          >
                            Approve
                          </button>
                          <button
                            className="btn"
                            onClick={() => setApproval(false)}
                            disabled={!canGenerate}
                          >
                            Reject
                          </button>
                        </div>
                        <input
                          className="w100"
                          value={handoffNote}
                          onChange={(event) => setHandoffNote(event.target.value)}
                          placeholder={
                            language === 'en'
                              ? 'Handoff note (required for blocked/handed_off)'
                              : 'Handoff-Notiz (für blocked/handed_off erforderlich)'
                          }
                        />
                        <div className="control-row">
                          <button
                            className="btn"
                            onClick={() => setHandoff('ready_for_send')}
                            disabled={!canGenerate}
                          >
                            Ready
                          </button>
                          <button
                            className="btn"
                            onClick={() => setHandoff('blocked')}
                            disabled={!canGenerate}
                          >
                            Block
                          </button>
                          <button
                            className="btn"
                            onClick={() => setHandoff('handed_off')}
                            disabled={!canGenerate}
                          >
                            Handed Off
                          </button>
                        </div>
                      </div>
                    )}

                    <hr />

                    <div className="muted small">
                      {language === 'en' ? 'Follow-up questions' : 'Rückfragen'}
                    </div>
                    <ul className="ul-tight">
                      {questions.length ? (
                        questions.map((q, i) => <li key={i}>{q}</li>)
                      ) : (
                        <li className="muted">{language === 'en' ? 'None.' : 'Keine.'}</li>
                      )}
                    </ul>

                    {questions.length > 0 && (
                      <div className="stack section-gap">
                        {questions.map((q, i) => (
                          <div key={i}>
                            <div className="muted small">{q}</div>
                            <input
                              className="w100"
                              aria-label={`Antwort auf Frage ${i + 1}`}
                              value={answers[i] || ''}
                              onChange={(e) =>
                                setAnswers((prev) => ({ ...prev, [i]: e.target.value }))
                              }
                              placeholder={language === 'en' ? 'Your answer…' : 'Deine Antwort…'}
                            />
                          </div>
                        ))}
                        <div>
                          <div className="muted small">
                            {language === 'en' ? 'Additional note (optional)' : 'Zusatz (optional)'}
                          </div>
                          <textarea
                            rows={3}
                            value={note}
                            onChange={(e) => setNote(e.target.value)}
                          />
                        </div>
                        <button
                          className="btn primary"
                          onClick={refine}
                          disabled={!canRefine || refining}
                        >
                          {refining ? '...' : 'Refine'}
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="card">
                  <div className="section-head">
                    <div>
                      <h3>AI Settings (Creator Profil)</h3>
                      <div className="muted small">
                        {language === 'en'
                          ? 'User-specific generation parameters including fallback logic and transparent preview.'
                          : 'Nutzerbezogene Parameter für die Generierung inkl. Fallback-Logik und transparenter Vorschau.'}
                      </div>
                    </div>
                    <button
                      className="btn"
                      onClick={saveCreatorProfile}
                      disabled={!canGenerate || settingsSaving}
                    >
                      {settingsSaving
                        ? language === 'en'
                          ? 'Saving…'
                          : 'Speichere…'
                        : language === 'en'
                          ? 'Save profile'
                          : 'Profil speichern'}
                    </button>
                  </div>

                  <div className="deal-fields-grid section-gap">
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Profile name' : 'Profilname'}
                      </span>
                      <input
                        value={profileName}
                        onChange={(event) => setProfileName(event.target.value)}
                        placeholder="z.B. Creator Hauptprofil"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Legal name (required)' : 'Klarname (Pflicht)'}
                      </span>
                      <input
                        value={profileClearName}
                        onChange={(event) => setProfileClearName(event.target.value)}
                        placeholder="Vorname Nachname"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Artist name (required)' : 'Künstlername (Pflicht)'}
                      </span>
                      <input
                        value={profileArtistName}
                        onChange={(event) => setProfileArtistName(event.target.value)}
                        placeholder="Creator Alias"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Channel link (required)' : 'Kanallink (Pflicht)'}
                      </span>
                      <input
                        value={profileChannelLink}
                        onChange={(event) => setProfileChannelLink(event.target.value)}
                        placeholder="https://..."
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Themes (CSV, required)' : 'Themen (CSV, Pflicht)'}
                      </span>
                      <input
                        value={profileThemesCsv}
                        onChange={(event) => setProfileThemesCsv(event.target.value)}
                        placeholder="beauty, lifestyle"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en'
                          ? 'Platforms (CSV, required)'
                          : 'Plattformen (CSV, Pflicht)'}
                      </span>
                      <input
                        value={profilePlatformsCsv}
                        onChange={(event) => setProfilePlatformsCsv(event.target.value)}
                        placeholder="youtube, instagram"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Tone' : 'Tonalitaet'}
                      </span>
                      <select
                        value={profileTone}
                        onChange={(event) =>
                          setProfileTone(event.target.value as typeof profileTone)
                        }
                      >
                        <option value="neutral">neutral</option>
                        <option value="friendly">friendly</option>
                        <option value="professional">professional</option>
                        <option value="energetic">energetic</option>
                        <option value="direct">direct</option>
                      </select>
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Target audience' : 'Zielgruppe'}
                      </span>
                      <input
                        value={profileTargetAudience}
                        onChange={(event) => setProfileTargetAudience(event.target.value)}
                        placeholder="z.B. Gen Z"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Language' : 'Sprache'}
                      </span>
                      <input
                        value={profileLanguageCode}
                        onChange={(event) => setProfileLanguageCode(event.target.value)}
                        placeholder="de oder en-US"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Content focus (CSV)' : 'Content-Schwerpunkte (CSV)'}
                      </span>
                      <input
                        value={profileContentFocusCsv}
                        onChange={(event) => setProfileContentFocusCsv(event.target.value)}
                        placeholder="community, storytelling"
                      />
                    </div>
                  </div>

                  <div className="stack section-gap">
                    <span className="muted small">
                      {language === 'en'
                        ? 'Short description (optional)'
                        : 'Kurzbeschreibung (optional)'}
                    </span>
                    <textarea
                      rows={3}
                      value={profileShortDescription}
                      onChange={(event) => setProfileShortDescription(event.target.value)}
                    />
                  </div>

                  {settingsPreview && (
                    <div className="stack section-gap">
                      <div className="muted small">
                        {language === 'en' ? 'Active settings source' : 'Aktive Settings-Quelle'}:{' '}
                        <strong>{settingsPreview.source}</strong>
                      </div>
                      <div className="muted small">
                        {language === 'en' ? 'Profile' : 'Profil'}:{' '}
                        {settingsPreview.profile_name ||
                          (language === 'en' ? '(not configured)' : '(nicht konfiguriert)')}
                      </div>
                      {!!settingsPreview.missing_required.length && (
                        <div className="error small">
                          {language === 'en'
                            ? 'Missing required fields. AI generation is blocked until the profile is complete.'
                            : 'Fehlende Pflichtfelder. AI-Generierung ist blockiert, bis das Profil vollständig ist.'}
                          : {settingsPreview.missing_required.join(', ')}
                        </div>
                      )}
                      <div className="prebox prebox-scroll">
                        {JSON.stringify(settingsPreview.applied_settings, null, 2)}
                      </div>
                    </div>
                  )}
                </div>

                <div className="card">
                  <div className="section-head">
                    <div>
                      <h3>Template Management</h3>
                      <div className="muted small">
                        {language === 'en'
                          ? 'Thread-specific templates for consistent replies.'
                          : 'Thread-spezifische Vorlagen für konsistente Antworten.'}
                      </div>
                    </div>
                  </div>
                  <div className="deal-fields-grid section-gap">
                    <div className="stack">
                      <span className="muted small">Template Name</span>
                      <input
                        value={templateName}
                        onChange={(event) => setTemplateName(event.target.value)}
                        placeholder="z.B. Sponsoring Erstantwort"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">Template Subject (optional)</span>
                      <input
                        value={templateSubject}
                        onChange={(event) => setTemplateSubject(event.target.value)}
                        placeholder={language === 'en' ? 'Subject template' : 'Betreff-Vorlage'}
                      />
                    </div>
                  </div>
                  <div className="stack section-gap">
                    <span className="muted small">Template Body</span>
                    <textarea
                      rows={4}
                      value={templateBody}
                      onChange={(event) => setTemplateBody(event.target.value)}
                      placeholder={language === 'en' ? 'Template body' : 'Vorlageninhalt'}
                    />
                    <button
                      className="btn"
                      onClick={saveTemplate}
                      disabled={
                        !canGenerate ||
                        templateSaving ||
                        !templateName.trim() ||
                        !templateBody.trim()
                      }
                    >
                      {templateSaving
                        ? language === 'en'
                          ? 'Saving…'
                          : 'Speichere…'
                        : language === 'en'
                          ? 'Save template'
                          : 'Template speichern'}
                    </button>
                  </div>
                </div>

                <div className="card">
                  <div className="section-head">
                    <div>
                      <h3>Redaktion</h3>
                      <div className="muted small">
                        {language === 'en'
                          ? 'Manual changes create a new version history and reset approval.'
                          : 'Manuelle Änderungen speichern eine neue Versionshistorie und setzen Freigabe zurück.'}
                      </div>
                    </div>
                  </div>
                  {currentDraft && (
                    <div className="stack section-gap">
                      <div className="stack">
                        <span className="muted small">Draft Subject</span>
                        <input
                          value={draftSubjectEdit}
                          onChange={(event) => setDraftSubjectEdit(event.target.value)}
                        />
                      </div>
                      <div className="stack">
                        <span className="muted small">Draft Body</span>
                        <textarea
                          rows={6}
                          value={draftBodyEdit}
                          onChange={(event) => setDraftBodyEdit(event.target.value)}
                        />
                      </div>
                      <div className="stack">
                        <span className="muted small">
                          {language === 'en'
                            ? 'Change reason (optional)'
                            : 'Änderungsgrund (optional)'}
                        </span>
                        <input
                          value={draftEditReason}
                          onChange={(event) => setDraftEditReason(event.target.value)}
                        />
                      </div>
                      <button
                        className="btn"
                        onClick={saveDraftEdits}
                        disabled={!canGenerate || draftSaving || !draftBodyEdit.trim()}
                      >
                        {draftSaving
                          ? language === 'en'
                            ? 'Saving…'
                            : 'Speichere…'
                          : language === 'en'
                            ? 'Save editorial draft'
                            : 'Redaktion speichern'}
                      </button>
                    </div>
                  )}
                </div>

                <div className="card">
                  <div className="section-head">
                    <div>
                      <h3>Versionen & Audit</h3>
                      <div className="muted small">
                        Nachvollziehbarkeit von AI/System-Vorschlaegen und Entscheidungen.
                      </div>
                    </div>
                  </div>
                  {currentDraft && (
                    <div className="stack section-gap">
                      <div>
                        <div className="muted small">Draft-Versionen</div>
                        {versionsForCurrentDraft.length === 0 ? (
                          <div className="muted small">
                            {language === 'en' ? 'No version entries.' : 'Keine Versionseintraege.'}
                          </div>
                        ) : (
                          <div className="stack">
                            {versionsForCurrentDraft.map((version) => (
                              <div key={version.id} className="message-pill system">
                                <div className="row between">
                                  <span className="muted small">
                                    v{version.version_number} · {formatDate(version.created_at)}
                                  </span>
                                  <span className="muted small">
                                    {version.changed_by_name || 'system'}
                                  </span>
                                </div>
                                <div className="muted small">
                                  {version.change_reason ||
                                    (language === 'en' ? 'no note' : 'keine Notiz')}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="muted small">Wissensgrundlage</div>
                        {knowledgeEvidenceForCurrentDraft.length === 0 ? (
                          <div className="muted small">
                            {language === 'en'
                              ? 'No linked knowledge documents.'
                              : 'Keine verknüpften Knowledge-Dokumente.'}
                          </div>
                        ) : (
                          <div className="stack">
                            {knowledgeEvidenceForCurrentDraft.map((entry) => (
                              <div
                                key={`${entry.draft_id}:${entry.knowledge_doc_id}`}
                                className="message-pill system"
                              >
                                <div className="row between">
                                  <span className="muted small">
                                    {entry.knowledge_doc_type} · {formatDate(entry.linked_at)}
                                  </span>
                                  <span className="muted small">
                                    {entry.linked_by_name || 'system'}
                                  </span>
                                </div>
                                <div className="muted small">{entry.knowledge_doc_title}</div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                      <div>
                        <div className="muted small">Suggestion-Audit</div>
                        {suggestionsForCurrentDraft.length === 0 ? (
                          <div className="muted small">
                            {language === 'en'
                              ? 'No suggestion entries.'
                              : 'Keine Suggestion-Eintraege.'}
                          </div>
                        ) : (
                          <div className="stack">
                            {suggestionsForCurrentDraft.map((suggestion) => (
                              <div key={suggestion.id} className="message-pill assistant">
                                <div className="row between">
                                  <span className="muted small">
                                    {suggestion.suggestion_type} ·{' '}
                                    {formatDate(suggestion.created_at)}
                                  </span>
                                  <span className="muted small">{suggestion.source}</span>
                                </div>
                                <div className="muted small">
                                  {suggestion.summary ||
                                    (language === 'en' ? 'no summary' : 'keine Zusammenfassung')}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>

                <div className="card">
                  <div className="section-head">
                    <div>
                      <h3>{language === 'en' ? 'Deal intake' : 'Deal Intake'}</h3>
                      <div className="muted small">
                        {hasDealDraft
                          ? language === 'en'
                            ? 'Deal draft saved'
                            : 'Deal Draft gespeichert'
                          : language === 'en'
                            ? 'No deal draft yet'
                            : 'Noch kein Deal Draft'}{' '}
                        · {language === 'en' ? 'Intent' : 'Intent'}: {threadDetail.detected_intent}
                      </div>
                      {!isSponsoringIntent && (
                        <div className="muted small">
                          {language === 'en'
                            ? 'Auto-analysis works best for sponsorship emails.'
                            : 'Auto-Analyse liefert beste Ergebnisse bei Sponsoring-Mails.'}
                        </div>
                      )}
                    </div>
                    <div className="control-row">
                      <button
                        className="btn"
                        onClick={autoFillDealDraft}
                        disabled={!canManageDeals || dealAutoLoading || !threadDetail}
                      >
                        {dealAutoLoading
                          ? language === 'en'
                            ? 'Analyzing…'
                            : 'Analysiere…'
                          : language === 'en'
                            ? 'Auto from email'
                            : 'Auto aus Mail'}
                      </button>
                      <button
                        className="btn primary"
                        onClick={saveDealDraft}
                        disabled={!canManageDeals || dealSaving || !threadDetail}
                      >
                        {dealSaving
                          ? language === 'en'
                            ? 'Saving…'
                            : 'Speichere…'
                          : hasDealDraft
                            ? language === 'en'
                              ? 'Update'
                              : 'Update'
                            : language === 'en'
                              ? 'Save'
                              : 'Speichern'}
                      </button>
                    </div>
                  </div>

                  {!canManageDeals && (
                    <div className="muted small">
                      {language === 'en'
                        ? 'No permission for deal intake editing.'
                        : 'Keine Berechtigung für Deal-Intake-Bearbeitung.'}
                    </div>
                  )}

                  {dealErr && <div className="error small mt8">{dealErr}</div>}

                  <div className="deal-fields-grid section-gap">
                    <div className="stack">
                      <span className="muted small">Brand</span>
                      <input
                        value={dealForm.brand_name}
                        onChange={(e) => updateDealField('brand_name', e.target.value)}
                        placeholder={language === 'en' ? 'Brand' : 'Marke'}
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Contact' : 'Kontakt'}
                      </span>
                      <input
                        value={dealForm.contact_name}
                        onChange={(e) => updateDealField('contact_name', e.target.value)}
                        placeholder={language === 'en' ? 'Name' : 'Name'}
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">
                        {language === 'en' ? 'Contact email' : 'Kontakt E-Mail'}
                      </span>
                      <input
                        value={dealForm.contact_email}
                        onChange={(e) => updateDealField('contact_email', e.target.value)}
                        placeholder="brand@example.com"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">Budget</span>
                      <input
                        value={dealForm.budget}
                        onChange={(e) => updateDealField('budget', e.target.value)}
                        placeholder={language === 'en' ? 'e.g. EUR 2,500' : 'z.B. 2.500 EUR'}
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">Status</span>
                      <select
                        value={dealForm.status}
                        onChange={(e) => updateDealStatus(e.target.value as DealDraftStatus)}
                      >
                        {dealStatusOptions.map((opt) => (
                          <option key={opt.value} value={opt.value}>
                            {opt.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  <div className="deal-fields-grid-large section-gap">
                    <div className="stack">
                      <span className="muted small">Deliverables</span>
                      <textarea
                        rows={3}
                        value={dealForm.deliverables}
                        onChange={(e) => updateDealField('deliverables', e.target.value)}
                        placeholder={
                          language === 'en'
                            ? 'e.g. 1x YouTube integration; 2x Stories'
                            : 'z.B. 1x YT Integration; 2x Stories'
                        }
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">Usage Rights</span>
                      <textarea
                        rows={3}
                        value={dealForm.usage_rights}
                        onChange={(e) => updateDealField('usage_rights', e.target.value)}
                        placeholder={
                          language === 'en'
                            ? 'Paid social 3 months; newsletter'
                            : 'Paid Social 3 Monate; Newsletter'
                        }
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">Deadlines</span>
                      <textarea
                        rows={3}
                        value={dealForm.deadlines}
                        onChange={(e) => updateDealField('deadlines', e.target.value)}
                        placeholder="Briefing: 12.03; Publish: 28.03"
                      />
                    </div>
                    <div className="stack">
                      <span className="muted small">Notes</span>
                      <textarea
                        rows={3}
                        value={dealForm.notes}
                        onChange={(e) => updateDealField('notes', e.target.value)}
                        placeholder={
                          language === 'en'
                            ? 'Additional constraints, approvals, etc.'
                            : 'Zusätzliche Auflagen, Freigaben, etc.'
                        }
                      />
                    </div>
                  </div>
                </div>

                {currentDraft && compareOptions.length > 0 && (
                  <div className="card">
                    <div className="section-head">
                      <h3>{language === 'en' ? 'Comparison' : 'Vergleich'}</h3>
                      <select
                        aria-label={
                          language === 'en'
                            ? 'Choose draft comparison'
                            : 'Draft-Vergleich auswählen'
                        }
                        value={compareDraftId || ''}
                        onChange={(e) => setCompareDraftId(e.target.value || null)}
                      >
                        {compareOptions.map((opt) => (
                          <option value={opt.id} key={opt.id}>
                            {formatDate(opt.created_at)} · {opt.tone}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="comparison-grid">
                      <div className="comparison-column">
                        <div className="comparison-header">
                          <strong>{language === 'en' ? 'Before' : 'Vorher'}</strong>
                          <span className="muted small">
                            {compareDraft ? formatDate(compareDraft.created_at) : ''}
                          </span>
                        </div>
                        {compareDraft ? (
                          <>
                            <div className="muted small">Subject</div>
                            <div className="prebox comparison-pre">
                              {compareDraft.draft_subject ||
                                (language === 'en' ? '(empty)' : '(leer)')}
                            </div>
                            <div className="muted small">Body</div>
                            <div className="prebox comparison-pre">{compareDraft.draft_body}</div>
                          </>
                        ) : (
                          <div className="muted">
                            {language === 'en'
                              ? 'Choose a draft to compare.'
                              : 'Wähle einen Draft zum Vergleich.'}
                          </div>
                        )}
                      </div>

                      <div className="comparison-column">
                        <div className="comparison-header">
                          <strong>{language === 'en' ? 'Current' : 'Neu'}</strong>
                          <span className="muted small">{formatDate(currentDraft.created_at)}</span>
                        </div>
                        <div className="muted small">Subject</div>
                        <div className="prebox comparison-pre">
                          {currentDraft.draft_subject || (language === 'en' ? '(empty)' : '(leer)')}
                        </div>
                        <div className="muted small">Body</div>
                        <div className="prebox comparison-pre">{currentDraft.draft_body}</div>
                      </div>
                    </div>
                  </div>
                )}

                <div>
                  <h3>{language === 'en' ? 'History' : 'Verlauf'}</h3>
                  <div className="stack">
                    {threadDetail.messages.length === 0 && (
                      <div className="muted">
                        {language === 'en' ? 'No history yet.' : 'Noch kein Verlauf.'}
                      </div>
                    )}
                    {threadDetail.messages.map((msg) => (
                      <div key={msg.id} className={`message-pill ${msg.role}`}>
                        <div className="row between">
                          <span className="muted small">
                            {msg.role} · {formatDate(msg.created_at)}
                          </span>
                          {typeof msg.payload?.action === 'string' && (
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
