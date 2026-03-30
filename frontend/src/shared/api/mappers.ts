import type {
  ContentTaskDto,
  DashboardProductVm,
  DashboardTaskVm,
  KnowledgeDocDto,
  KnowledgeDocVm,
  ProductAssetDto,
  ProductAssetVm,
  ProductDetailVm,
  ProductDto,
  ProductListItemVm,
  ProductTransactionDto,
  ProductTransactionVm,
} from './contracts'

export function toProductListItemVm(dto: ProductDto): ProductListItemVm {
  return {
    id: dto.id,
    title: dto.title,
    category: dto.category ?? '',
    condition: dto.condition ?? '',
    status: dto.status,
    currentValue: dto.current_value,
    currency: dto.currency ?? '',
  }
}

export function toProductDetailVm(dto: ProductDto): ProductDetailVm {
  return {
    id: dto.id,
    title: dto.title,
    brand: dto.brand ?? '',
    model: dto.model ?? '',
    status: dto.status,
    condition: dto.condition ?? '',
    currentValue: dto.current_value,
    currency: dto.currency ?? '',
    notes: dto.notes_md ?? '',
  }
}

export function toProductAssetVm(dto: ProductAssetDto): ProductAssetVm {
  return {
    id: dto.id,
    title: dto.title ?? '',
    source: dto.source ?? '',
    reviewState: dto.review_state,
    isPrimary: dto.is_primary,
    licenseType: dto.license_type ?? '',
    attribution: dto.attribution ?? '',
    sourceUrl: dto.source_url ?? '',
    licenseUrl: dto.license_url ?? '',
  }
}

export function toProductTransactionVm(dto: ProductTransactionDto): ProductTransactionVm {
  return {
    id: dto.id,
    txType: dto.tx_type,
    txDate: dto.tx_date ?? '',
    amount: dto.amount,
    currency: dto.currency ?? '',
    note: dto.note ?? '',
  }
}

export function toKnowledgeDocVm(dto: KnowledgeDocDto): KnowledgeDocVm {
  const versions = (dto.versions ?? []).map(version => ({
    id: version.id,
    versionNumber: version.version_number,
    title: version.title,
    type: version.type,
    workflowStatus: version.workflow_status,
    sourceReviewStatus: version.source_review_status,
    trustLevel: version.trust_level,
    isOutdated: version.is_outdated,
    changeNote: version.change_note ?? '',
    changedByName: version.changed_by_name ?? '',
    createdAt: version.created_at,
  })).sort((a, b) => b.versionNumber - a.versionNumber)

  const draftLinks = (dto.draft_links ?? []).map(link => ({
    id: link.id,
    emailDraftId: link.email_draft_id,
    linkedAt: link.linked_at,
    linkedByName: link.linked_by_name ?? '',
  })).sort((a, b) => {
    const aTs = Date.parse(a.linkedAt || '')
    const bTs = Date.parse(b.linkedAt || '')
    return (Number.isFinite(bTs) ? bTs : 0) - (Number.isFinite(aTs) ? aTs : 0)
  })

  return {
    id: dto.id,
    type: dto.type,
    title: dto.title,
    content: dto.content,
    workflowStatus: dto.workflow_status ?? 'draft',
    reviewReason: dto.review_reason ?? '',
    sourceName: dto.source_name ?? '',
    sourceUrl: dto.source_url ?? '',
    sourceType: dto.source_type ?? 'internal',
    sourceReviewStatus: dto.source_review_status ?? 'pending',
    sourceReviewNote: dto.source_review_note ?? '',
    originSummary: dto.origin_summary ?? '',
    trustLevel: dto.trust_level ?? 'medium',
    isOutdated: dto.is_outdated ?? false,
    outdatedReason: dto.outdated_reason ?? '',
    outdatedAt: dto.outdated_at ?? '',
    currentVersion: dto.current_version ?? 1,
    versions,
    draftLinks,
  }
}

export function toDashboardProductVm(dto: ProductDto): DashboardProductVm {
  return {
    id: dto.id,
    title: dto.title,
    status: dto.status,
    quantity: dto.quantity ?? 1,
    currentValue: dto.current_value ?? 0,
    updatedAt: dto.updated_at ?? '',
  }
}

export function toDashboardTaskVm(dto: ContentTaskDto): DashboardTaskVm {
  return {
    id: dto.id,
    title: dto.title,
    status: dto.status,
    updatedAt: dto.updated_at ?? '',
  }
}
