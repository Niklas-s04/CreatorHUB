import { describe, expect, it } from 'vitest'
import {
  toDashboardProductVm,
  toKnowledgeDocVm,
  toProductAssetVm,
  toProductDetailVm,
  toProductListItemVm,
  toProductTransactionVm,
} from './mappers'

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
      purchase_price: 99.5,
      purchase_date: '2024-01-02',
      current_value: 123,
      currency: null,
      storage_location: 'Studio',
      serial_number: 'SN-7',
      notes_md: null,
      quantity: 2,
      workflow_status: 'review',
      review_reason: 'Check license',
      project_ids: ['project-1'],
      status_changed_at: '2024-01-03T00:00:00Z',
      reviewed_by_id: 'user-1',
      reviewed_by_name: 'Alice',
      reviewed_at: '2024-01-04T00:00:00Z',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-05T00:00:00Z',
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
      category: '',
      status: 'active',
      condition: '',
      purchasePrice: 99.5,
      purchaseDate: '2024-01-02',
      currentValue: 123,
      currency: '',
      storageLocation: 'Studio',
      serialNumber: 'SN-7',
      quantity: 2,
      notes: '',
      workflowStatus: 'review',
      reviewReason: 'Check license',
      projectIds: ['project-1'],
      statusChangedAt: '2024-01-03T00:00:00Z',
      reviewedById: 'user-1',
      reviewedByName: 'Alice',
      reviewedAt: '2024-01-04T00:00:00Z',
      createdAt: '2024-01-01T00:00:00Z',
      updatedAt: '2024-01-05T00:00:00Z',
    })
  })

  it('maps assets, transactions, dashboard and knowledge docs', () => {
    expect(
      toProductAssetVm({
        id: 'asset-1',
        title: null,
        source: null,
        review_state: 'approved',
        is_primary: true,
        license_type: null,
        attribution: null,
        source_url: null,
        license_url: null,
      })
    ).toMatchObject({
      title: '',
      source: '',
      reviewState: 'approved',
      isPrimary: true,
    })
    expect(
      toProductTransactionVm({
        id: 'tx-2',
        product_id: 'product-2',
        type: 'buy',
        date: '2024-01-01',
        amount: null,
        currency: 'EUR',
        counterparty: null,
        notes: null,
      })
    ).toMatchObject({ txType: 'buy', txDate: '2024-01-01', currency: 'EUR', note: '' })
    expect(
      toDashboardProductVm({
        id: 'product-3',
        title: 'X',
        brand: null,
        model: null,
        category: null,
        condition: null,
        status: 'sold',
        purchase_price: null,
        purchase_date: null,
        current_value: null,
        currency: null,
        storage_location: null,
        serial_number: null,
        quantity: null,
        notes_md: null,
        workflow_status: null,
        review_reason: null,
        project_ids: [],
        status_changed_at: null,
        reviewed_by_id: null,
        reviewed_by_name: null,
        reviewed_at: null,
        created_at: null,
        updated_at: null,
      })
    ).toMatchObject({ quantity: 1, currentValue: 0, updatedAt: '' })

    const docVm = toKnowledgeDocVm({
      id: 'doc-1',
      type: 'policy',
      title: 'Policy',
      content: 'text',
      versions: [
        {
          id: 'v1',
          version_number: 1,
          title: 'v1',
          type: 'policy',
          workflow_status: 'draft',
          source_review_status: 'pending',
          trust_level: 'medium',
          is_outdated: false,
          change_note: null,
          changed_by_name: null,
          created_at: '2024-01-01T00:00:00Z',
        },
        {
          id: 'v2',
          version_number: 2,
          title: 'v2',
          type: 'policy',
          workflow_status: 'published',
          source_review_status: 'approved',
          trust_level: 'high',
          is_outdated: false,
          change_note: null,
          changed_by_name: null,
          created_at: '2024-01-02T00:00:00Z',
        },
      ],
      draft_links: [
        { id: 'l1', email_draft_id: 'd1', linked_at: '2024-01-02T00:00:00Z', linked_by_name: null },
      ],
    })

    expect(docVm.versions[0].versionNumber).toBe(2)
    expect(docVm.draftLinks[0].linkedByName).toBe('')
  })
})
