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
  return {
    id: dto.id,
    type: dto.type,
    title: dto.title,
    content: dto.content,
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
