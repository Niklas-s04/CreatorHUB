import { describe, expect, it } from 'vitest'
import {
  parseContentTasksDtoArray,
  parseImageSearchJobDto,
  parseKnowledgeDocsPage,
  parseProductAssetsDtoArray,
  parseProductDto,
  parseProductTransactionsDtoArray,
} from './validators'

describe('validators', () => {
  it('parses product and related arrays', () => {
    expect(
      parseProductDto({
        id: 'product-1',
        category: 'Camera',
        purchase_price: 1499,
        purchase_date: '2024-02-03',
        storage_location: 'Shelf A',
        serial_number: 'SERIAL-1',
        quantity: 2,
        currency: 'USD',
        project_ids: ['project-1', 4],
      })
    ).toMatchObject({
      id: 'product-1',
      title: 'Unbenanntes Produkt',
      status: 'active',
      category: 'Camera',
      purchase_price: 1499,
      purchase_date: '2024-02-03',
      storage_location: 'Shelf A',
      serial_number: 'SERIAL-1',
      quantity: 2,
      currency: 'USD',
      project_ids: ['project-1'],
    })
    expect(parseProductAssetsDtoArray([{ id: 'asset-1', review_state: 'bad' }])[0]).toMatchObject({
      id: 'asset-1',
      review_state: 'pending',
      is_primary: false,
    })
    expect(
      parseProductTransactionsDtoArray([
        {
          id: 'tx-1',
          product_id: 'product-1',
          type: 'purchase',
          date: '2026-07-23',
          amount: 4,
          currency: 'EUR',
          counterparty: 'Store',
          notes: 'Receipt',
        },
      ])[0]
    ).toEqual({
      id: 'tx-1',
      product_id: 'product-1',
      type: 'purchase',
      date: '2026-07-23',
      amount: 4,
      currency: 'EUR',
      counterparty: 'Store',
      notes: 'Receipt',
    })
    expect(parseContentTasksDtoArray([{ id: 'task-1', title: null }])[0]).toMatchObject({
      id: 'task-1',
      title: 'Neue Aufgabe',
    })
  })

  it('parses knowledge docs and image search jobs', () => {
    const docs = parseKnowledgeDocsPage({ items: [{ id: 'd', title: 'Doc', content: 'c' }] })
    expect(docs[0].current_version).toBe(1)

    expect(
      parseImageSearchJobDto({
        status: 'unknown',
        result: { query: 'q', count: 2, candidates: [] },
      })
    ).toMatchObject({ status: 'queued', result: { query: 'q', count: 2 } })
  })
})
