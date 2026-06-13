import { describe, expect, it } from 'vitest'
import { toDashboardProductVm, toKnowledgeDocVm, toProductAssetVm, toProductDetailVm, toProductListItemVm, toProductTransactionVm } from './mappers'

describe('mappers', () => {
  it('maps product dto to list and detail view models', () => {
    const dto = {
      id: 'product-7',
      title: 'Cam',
      brand: null,
      model: null,
      category: null,
      condition: null,
      status: 'active' as const,
      current_value: 123,
      currency: null,
      notes_md: null,
      quantity: null,
      updated_at: null,
    }

    expect(toProductListItemVm(dto)).toEqual({
      id: 'product-7',
      title: 'Cam',
      category: '',
      condition: '',
      status: 'active',
      currentValue: 123,
      currency: '',
    })
    expect(toProductDetailVm(dto)).toEqual({
      id: 'product-7',
      title: 'Cam',
      brand: '',
      model: '',
      status: 'active',
      condition: '',
      currentValue: 123,
      currency: '',
      notes: '',
    })
  })

  it('maps assets, transactions, dashboard and knowledge docs', () => {
    expect(toProductAssetVm({ id: 'asset-1', title: null, source: null, review_state: 'approved', is_primary: true, license_type: null, attribution: null, source_url: null, license_url: null })).toMatchObject({
      title: '',
      source: '',
      reviewState: 'approved',
      isPrimary: true,
    })
    expect(toProductTransactionVm({ id: 'tx-2', tx_type: 'buy', tx_date: null, amount: null, currency: null, note: null })).toMatchObject({ txDate: '', currency: '', note: '' })
    expect(
      toDashboardProductVm({
        id: 'product-3',
        title: 'X',
        brand: null,
        model: null,
        category: null,
        condition: null,
        status: 'sold',
        current_value: null,
        currency: null,
        quantity: null,
        notes_md: null,
        updated_at: null,
      })
    ).toMatchObject({ quantity: 1, currentValue: 0, updatedAt: '' })

    const docVm = toKnowledgeDocVm({
      id: 'doc-1',
      type: 'policy',
      title: 'Policy',
      content: 'text',
      versions: [
        { id: 'v1', version_number: 1, title: 'v1', type: 'policy', workflow_status: 'draft', source_review_status: 'pending', trust_level: 'medium', is_outdated: false, change_note: null, changed_by_name: null, created_at: '2024-01-01T00:00:00Z' },
        { id: 'v2', version_number: 2, title: 'v2', type: 'policy', workflow_status: 'published', source_review_status: 'approved', trust_level: 'high', is_outdated: false, change_note: null, changed_by_name: null, created_at: '2024-01-02T00:00:00Z' },
      ],
      draft_links: [{ id: 'l1', email_draft_id: 'd1', linked_at: '2024-01-02T00:00:00Z', linked_by_name: null }],
    })

    expect(docVm.versions[0].versionNumber).toBe(2)
    expect(docVm.draftLinks[0].linkedByName).toBe('')
  })
})
