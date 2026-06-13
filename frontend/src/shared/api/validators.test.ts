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
    expect(parseProductDto({ id: 'product-1' })).toMatchObject({
      id: 'product-1',
      title: 'Unbenanntes Produkt',
      status: 'active',
    })
    expect(parseProductAssetsDtoArray([{ id: 'asset-1', review_state: 'bad' }])[0]).toMatchObject({
      id: 'asset-1',
      review_state: 'pending',
      is_primary: false,
    })
    expect(parseProductTransactionsDtoArray([{ id: 'tx-1', amount: 4 }])[0]).toMatchObject({ id: 'tx-1', amount: 4 })
    expect(parseContentTasksDtoArray([{ id: 'task-1', title: null }])[0]).toMatchObject({
      id: 'task-1',
      title: 'Neue Aufgabe',
    })
  })

  it('parses knowledge docs and image search jobs', () => {
    const docs = parseKnowledgeDocsPage({ items: [{ id: 'd', title: 'Doc', content: 'c' }] })
    expect(docs[0].current_version).toBe(1)

    expect(
      parseImageSearchJobDto({ status: 'unknown', result: { query: 'q', count: 2, candidates: [] } })
    ).toMatchObject({ status: 'queued', result: { query: 'q', count: 2 } })
  })
})
