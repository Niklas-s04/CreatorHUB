import type {
  ContentTaskDto,
  ImageSearchJobDto,
  KnowledgeDocDto,
  ProductAssetDto,
  ProductDto,
  ProductStatusDto,
  ProductTransactionDto,
} from './contracts'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asNullableString(value: unknown): string | null {
  return typeof value === 'string' ? value : null
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function asProductStatus(value: unknown): ProductStatusDto {
  const raw = asString(value)
  return raw === 'active' || raw === 'sold' || raw === 'gifted' || raw === 'returned' || raw === 'broken' || raw === 'archived'
    ? raw
    : 'active'
}

function asReviewState(value: unknown): 'pending' | 'approved' | 'rejected' {
  const raw = asString(value)
  return raw === 'approved' || raw === 'rejected' ? raw : 'pending'
}

export function parseProductsDtoArray(input: unknown): ProductDto[] {
  if (!Array.isArray(input)) return []
  return input.map(parseProductDto)
}

export function parseProductDto(input: unknown): ProductDto {
  const src = isRecord(input) ? input : {}
  return {
    id: asNumber(src.id, -1),
    title: asString(src.title, 'Unbenanntes Produkt'),
    brand: asNullableString(src.brand),
    model: asNullableString(src.model),
    category: asNullableString(src.category),
    condition: asNullableString(src.condition),
    status: asProductStatus(src.status),
    current_value: asNullableNumber(src.current_value),
    currency: asNullableString(src.currency),
    quantity: asNullableNumber(src.quantity),
    notes_md: asNullableString(src.notes_md),
    updated_at: asNullableString(src.updated_at),
  }
}

export function parseProductAssetsDtoArray(input: unknown): ProductAssetDto[] {
  if (!Array.isArray(input)) return []
  return input.map(item => {
    const src = isRecord(item) ? item : {}
    return {
      id: asNumber(src.id, -1),
      title: asNullableString(src.title),
      source: asNullableString(src.source),
      review_state: asReviewState(src.review_state),
      is_primary: asBoolean(src.is_primary),
      license_type: asNullableString(src.license_type),
      attribution: asNullableString(src.attribution),
      source_url: asNullableString(src.source_url),
      license_url: asNullableString(src.license_url),
    }
  })
}

export function parseProductTransactionsDtoArray(input: unknown): ProductTransactionDto[] {
  if (!Array.isArray(input)) return []
  return input.map(item => {
    const src = isRecord(item) ? item : {}
    return {
      id: asNumber(src.id, -1),
      tx_type: asString(src.tx_type, 'unknown'),
      tx_date: asNullableString(src.tx_date),
      amount: asNullableNumber(src.amount),
      currency: asNullableString(src.currency),
      note: asNullableString(src.note),
    }
  })
}

export function parseKnowledgeDocsDtoArray(input: unknown): KnowledgeDocDto[] {
  if (!Array.isArray(input)) return []
  return input.map(item => {
    const src = isRecord(item) ? item : {}
    const versionsRaw = Array.isArray(src.versions) ? src.versions : []
    const draftLinksRaw = Array.isArray(src.draft_links) ? src.draft_links : []
    return {
      id: asString(src.id, ''),
      type: asString(src.type, 'unknown'),
      title: asString(src.title, 'Ohne Titel'),
      content: asString(src.content, ''),
      workflow_status: asString(src.workflow_status, 'draft'),
      review_reason: asNullableString(src.review_reason),
      source_name: asNullableString(src.source_name),
      source_url: asNullableString(src.source_url),
      source_type: asString(src.source_type, 'internal'),
      source_review_status: asString(src.source_review_status, 'pending'),
      source_review_note: asNullableString(src.source_review_note),
      origin_summary: asNullableString(src.origin_summary),
      trust_level: asString(src.trust_level, 'medium'),
      is_outdated: asBoolean(src.is_outdated),
      outdated_reason: asNullableString(src.outdated_reason),
      outdated_at: asNullableString(src.outdated_at),
      current_version: asNumber(src.current_version, 1),
      versions: versionsRaw.map(version => {
        const versionSrc = isRecord(version) ? version : {}
        return {
          id: asString(versionSrc.id, ''),
          version_number: asNumber(versionSrc.version_number, 1),
          title: asString(versionSrc.title, 'Ohne Titel'),
          type: asString(versionSrc.type, 'unknown'),
          workflow_status: asString(versionSrc.workflow_status, 'draft'),
          source_review_status: asString(versionSrc.source_review_status, 'pending'),
          trust_level: asString(versionSrc.trust_level, 'medium'),
          is_outdated: asBoolean(versionSrc.is_outdated),
          change_note: asNullableString(versionSrc.change_note),
          changed_by_name: asNullableString(versionSrc.changed_by_name),
          created_at: asString(versionSrc.created_at, ''),
        }
      }),
      draft_links: draftLinksRaw.map(link => {
        const linkSrc = isRecord(link) ? link : {}
        return {
          id: asString(linkSrc.id, ''),
          email_draft_id: asString(linkSrc.email_draft_id, ''),
          linked_at: asString(linkSrc.linked_at, ''),
          linked_by_name: asNullableString(linkSrc.linked_by_name),
        }
      }),
    }
  })
}

export function parseKnowledgeDocsPage(input: unknown): KnowledgeDocDto[] {
  if (Array.isArray(input)) {
    return parseKnowledgeDocsDtoArray(input)
  }
  if (!isRecord(input) || !Array.isArray(input.items)) {
    return []
  }
  return parseKnowledgeDocsDtoArray(input.items)
}

export function parseContentTasksDtoArray(input: unknown): ContentTaskDto[] {
  if (!Array.isArray(input)) return []
  return input.map(item => {
    const src = isRecord(item) ? item : {}
    return {
      id: asNumber(src.id, -1),
      title: asString(src.title, 'Neue Aufgabe'),
      status: asString(src.status, 'todo'),
      updated_at: asNullableString(src.updated_at),
    }
  })
}

export function parseImageSearchJobDto(input: unknown): ImageSearchJobDto {
  const src = isRecord(input) ? input : {}
  const statusRaw = asString(src.status, 'queued')
  const status = statusRaw === 'running' || statusRaw === 'finished' || statusRaw === 'failed' ? statusRaw : 'queued'
  const result = isRecord(src.result)
    ? {
        query: asNullableString(src.result.query) ?? undefined,
        count: typeof src.result.count === 'number' ? src.result.count : undefined,
        candidates: Array.isArray(src.result.candidates) ? src.result.candidates : undefined,
      }
    : null

  return {
    status,
    result,
    error: asNullableString(src.error),
  }
}
