import { describe, expect, it } from 'vitest'
import type { ProductDetailVm } from '../../../../shared/api/contracts'
import { buildProductMasterPatch, masterFormsEqual, productToMasterForm } from './productMasterForm'

const product: ProductDetailVm = {
  id: 'product-1',
  title: 'Camera',
  brand: 'Acme',
  model: 'Pro',
  category: 'Video',
  status: 'active',
  condition: 'very_good',
  purchasePrice: 1299.5,
  purchaseDate: '2024-02-03',
  currentValue: 999,
  currency: 'USD',
  storageLocation: 'Studio A',
  serialNumber: 'SERIAL-42',
  quantity: 2,
  notes: 'Keep dry',
  workflowStatus: 'draft',
  reviewReason: '',
  projectIds: ['project-1'],
  statusChangedAt: '2024-02-03T12:00:00Z',
  reviewedById: '',
  reviewedByName: '',
  reviewedAt: '',
  createdAt: '2024-02-03T12:00:00Z',
  updatedAt: '2024-02-04T12:00:00Z',
}

describe('product master form', () => {
  it('initializes every editable field from the product contract', () => {
    expect(productToMasterForm(product)).toEqual({
      title: 'Camera',
      brand: 'Acme',
      model: 'Pro',
      category: 'Video',
      condition: 'very_good',
      storage_location: 'Studio A',
      serial_number: 'SERIAL-42',
      purchase_price: '1299.5',
      purchase_date: '2024-02-03',
      current_value: '999',
      currency: 'USD',
      notes_md: 'Keep dry',
    })
  })

  it('creates a title-only PATCH without nulling untouched product data', () => {
    const baseline = productToMasterForm(product)
    const edited = { ...baseline, title: 'Camera Mark II' }

    expect(masterFormsEqual(edited, baseline)).toBe(false)
    expect(buildProductMasterPatch(edited, baseline)).toEqual({
      title: 'Camera Mark II',
    })
  })

  it('rejects invalid monetary values instead of serializing them as null', () => {
    const baseline = productToMasterForm(product)

    expect(() =>
      buildProductMasterPatch({ ...baseline, current_value: 'not-a-number' }, baseline)
    ).toThrow('valid number')
    expect(() => buildProductMasterPatch({ ...baseline, purchase_price: '-1' }, baseline)).toThrow(
      'must not be negative'
    )
  })
})
