import type { ReactNode } from 'react'

import { PRODUCT_STATUS_OPTIONS } from '../../../../entities/product/model'
import { useI18n } from '../../../../shared/i18n/i18n'

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
  const { language } = useI18n()
  const from = total === 0 ? 0 : offset + 1
  const to = total === 0 ? 0 : Math.min(offset + itemCount, total)

  return (
    <div className="stack mb10">
      <div className="control-row flex1">
        <label className="sr-only" htmlFor="products-filter-query">
          {language === 'en' ? 'Product search' : 'Produktsuche'}
        </label>
        <input
          id="products-filter-query"
          className="grow"
          placeholder={language === 'en' ? 'Search…' : 'Suche…'}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
        />
        <label className="sr-only" htmlFor="products-filter-status">
          {language === 'en' ? 'Status filter' : 'Status-Filter'}
        </label>
        <select
          id="products-filter-status"
          value={status}
          onChange={(e) => onStatusChange(e.target.value)}
        >
          <option value="">{language === 'en' ? 'Status: all' : 'Status: alle'}</option>
          {PRODUCT_STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
        <label className="sr-only" htmlFor="products-filter-page-size">
          {language === 'en' ? 'Page size' : 'Seitengröße'}
        </label>
        <select
          id="products-filter-page-size"
          value={String(pageSize)}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
        >
          <option value="25">25 {language === 'en' ? '/ page' : '/ Seite'}</option>
          <option value="50">50 {language === 'en' ? '/ page' : '/ Seite'}</option>
          <option value="60">60 {language === 'en' ? '/ page' : '/ Seite'}</option>
        </select>
        <button className="btn" onClick={onFilter}>
          {language === 'en' ? 'Filter' : 'Filter'}
        </button>
        <button className="btn ghost" onClick={onReset}>
          {language === 'en' ? 'Reset' : 'Reset'}
        </button>
      </div>
      <div className="row between">
        <span className="muted small" role="status" aria-live="polite" aria-atomic="true">
          {itemCount} {language === 'en' ? 'visible' : 'sichtbar'} · {from}-{to}{' '}
          {language === 'en' ? 'of' : 'von'} {total}
        </span>
        {extraActions}
      </div>
    </div>
  )
}
