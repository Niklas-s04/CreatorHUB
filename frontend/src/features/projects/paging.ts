import type { Page } from './model'

type PageFetcher<T> = (path: string) => Promise<Page<T>>

export async function fetchAllPages<T>(
  fetchPage: PageFetcher<T>,
  basePath: string,
  pageSize = 100
): Promise<T[]> {
  const items: T[] = []
  let offset = 0
  let total = Number.POSITIVE_INFINITY

  while (offset < total) {
    const separator = basePath.includes('?') ? '&' : '?'
    const page = await fetchPage(
      `${basePath}${separator}limit=${encodeURIComponent(String(pageSize))}&offset=${encodeURIComponent(
        String(offset)
      )}`
    )
    const pageItems = Array.isArray(page.items) ? page.items : []
    total = Number.isFinite(page.meta?.total) ? Math.max(0, page.meta.total) : pageItems.length

    if (!pageItems.length) {
      if (offset < total) {
        throw new Error(`Pagination ended before all ${total} entries were loaded.`)
      }
      break
    }

    items.push(...pageItems)
    const nextOffset = page.meta.offset + pageItems.length
    if (nextOffset <= offset) {
      throw new Error('Pagination did not advance.')
    }
    offset = nextOffset
  }

  return items
}
