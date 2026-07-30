import { describe, expect, it, vi } from 'vitest'
import type { Page } from './model'
import { fetchAllPages } from './paging'

function page<T>(items: T[], offset: number, total: number): Page<T> {
  return {
    items,
    meta: {
      limit: 100,
      offset,
      total,
      sort_by: 'updated_at',
      sort_order: 'desc',
    },
  }
}

describe('fetchAllPages', () => {
  it('continues with the API offset until every project is loaded', async () => {
    const firstPage = Array.from({ length: 100 }, (_, index) => `project-${index}`)
    const fetchPage = vi
      .fn()
      .mockResolvedValueOnce(page(firstPage, 0, 101))
      .mockResolvedValueOnce(page(['project-100'], 100, 101))

    await expect(
      fetchAllPages(fetchPage, '/projects?sort_by=due_date&sort_order=asc')
    ).resolves.toHaveLength(101)
    expect(fetchPage).toHaveBeenNthCalledWith(
      2,
      '/projects?sort_by=due_date&sort_order=asc&limit=100&offset=100'
    )
  })

  it('fails visibly when a paged response stops before its advertised total', async () => {
    const fetchPage = vi.fn().mockResolvedValue(page([], 0, 2))

    await expect(fetchAllPages(fetchPage, '/projects')).rejects.toThrow(
      'Pagination ended before all 2 entries were loaded.'
    )
  })
})
