import type { ReactNode } from 'react'

import { PRODUCT_STATUS_OPTIONS } from '../../../../entities/product/model'

type ProductsFilterBarProps = {
  query: string
  status: string
  pageSize: number
  total: number
  offset: number
  itemCount: number
  onQueryChange: (value: string) => void
  onStatusChange: (value: string) => void
  onPageSizeChange: (value: number) => void
  onFilter: () => void
  onReset: () => void
  extraActions?: ReactNode
}

export function ProductsFilterBar({
  query,
  status,
  pageSize,
  total,
  offset,
  itemCount,
  onQueryChange,
  onStatusChange,
  onPageSizeChange,
  onFilter,
  onReset,
  extraActions,
}: ProductsFilterBarProps) {
  const from = total === 0 ? 0 : offset + 1
  const to = total === 0 ? 0 : Math.min(offset + itemCount, total)

  return (
    <div className="stack mb10">
      <div className="control-row flex1">
        <label className="sr-only" htmlFor="products-filter-query">Produktsuche</label>
        <input id="products-filter-query" className="grow" placeholder="Suche…" value={query} onChange={e => onQueryChange(e.target.value)} />
        <label className="sr-only" htmlFor="products-filter-status">Status-Filter</label>
        <select id="products-filter-status" value={status} onChange={e => onStatusChange(e.target.value)}>
          <option value="">Status: alle</option>
          {PRODUCT_STATUS_OPTIONS.map(option => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
        <label className="sr-only" htmlFor="products-filter-page-size">Seitengröße</label>
        <select id="products-filter-page-size" value={String(pageSize)} onChange={e => onPageSizeChange(Number(e.target.value))}>
          <option value="25">25 / Seite</option>
          <option value="50">50 / Seite</option>
          <option value="60">60 / Seite</option>
        </select>
        <button className="btn" onClick={onFilter}>Filter</button>
        <button className="btn ghost" onClick={onReset}>Reset</button>
      </div>
      <div className="row between">
        <span className="muted small" role="status" aria-live="polite" aria-atomic="true">{itemCount} sichtbar · {from}-{to} von {total}</span>
        {extraActions}
      </div>
    </div>
  )
}
