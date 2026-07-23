import type { ProductDetailVm } from '../../../../shared/api/contracts'

export type ProductMasterForm = {
  title: string
  brand: string
  model: string
  category: string
  condition: string
  storage_location: string
  serial_number: string
  purchase_price: string
  purchase_date: string
  current_value: string
  currency: string
  notes_md: string
}

export type ProductMasterPatch = {
  title?: string
  brand?: string | null
  model?: string | null
  category?: string | null
  condition?: string
  storage_location?: string | null
  serial_number?: string | null
  purchase_price?: number | null
  purchase_date?: string | null
  current_value?: number | null
  currency?: string
  notes_md?: string | null
}

export function initialMasterForm(): ProductMasterForm {
  return {
    title: '',
    brand: '',
    model: '',
    category: '',
    condition: 'good',
    storage_location: '',
    serial_number: '',
    purchase_price: '',
    purchase_date: '',
    current_value: '',
    currency: 'EUR',
    notes_md: '',
  }
}

export function productToMasterForm(product: ProductDetailVm): ProductMasterForm {
  return {
    title: product.title,
    brand: product.brand,
    model: product.model,
    category: product.category,
    condition: product.condition || 'good',
    storage_location: product.storageLocation,
    serial_number: product.serialNumber,
    purchase_price: product.purchasePrice == null ? '' : String(product.purchasePrice),
    purchase_date: product.purchaseDate,
    current_value: product.currentValue == null ? '' : String(product.currentValue),
    currency: product.currency || 'EUR',
    notes_md: product.notes,
  }
}

export function masterFormsEqual(left: ProductMasterForm, right: ProductMasterForm): boolean {
  return (Object.keys(left) as Array<keyof ProductMasterForm>).every(
    (field) => left[field] === right[field]
  )
}

function nullableNumber(value: string): number | null {
  const normalized = value.trim().replace(',', '.')
  if (!normalized) return null
  const parsed = Number(normalized)
  if (!Number.isFinite(parsed)) {
    throw new Error('Value must be a valid number.')
  }
  if (parsed < 0) {
    throw new Error('Value must not be negative.')
  }
  return parsed
}

export function buildProductMasterPatch(
  form: ProductMasterForm,
  baseline: ProductMasterForm
): ProductMasterPatch {
  const patch: ProductMasterPatch = {}

  if (form.title !== baseline.title) patch.title = form.title.trim()
  if (form.brand !== baseline.brand) patch.brand = form.brand.trim() || null
  if (form.model !== baseline.model) patch.model = form.model.trim() || null
  if (form.category !== baseline.category) patch.category = form.category.trim() || null
  if (form.condition !== baseline.condition) patch.condition = form.condition
  if (form.storage_location !== baseline.storage_location) {
    patch.storage_location = form.storage_location.trim() || null
  }
  if (form.serial_number !== baseline.serial_number) {
    patch.serial_number = form.serial_number.trim() || null
  }
  if (form.purchase_price !== baseline.purchase_price) {
    patch.purchase_price = nullableNumber(form.purchase_price)
  }
  if (form.purchase_date !== baseline.purchase_date) {
    patch.purchase_date = form.purchase_date || null
  }
  if (form.current_value !== baseline.current_value) {
    patch.current_value = nullableNumber(form.current_value)
  }
  if (form.currency !== baseline.currency) patch.currency = form.currency.trim() || 'EUR'
  if (form.notes_md !== baseline.notes_md) patch.notes_md = form.notes_md || null

  return patch
}
