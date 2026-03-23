import { PRODUCT_STATUS_OPTIONS } from '../../../../entities/product/model'

type ProductsFilterBarProps = {
  query: string
  status: string
  itemCount: number
  onQueryChange: (value: string) => void
  onStatusChange: (value: string) => void
  onFilter: () => void
}

export function ProductsFilterBar({
  query,
  status,
  itemCount,
  onQueryChange,
  onStatusChange,
  onFilter,
}: ProductsFilterBarProps) {
  return (
    <div className="page-header mb10">
      <div className="control-row flex1">
        <input className="grow" placeholder="Suche…" value={query} onChange={e => onQueryChange(e.target.value)} />
        <select value={status} onChange={e => onStatusChange(e.target.value)}>
          <option value="">Status: alle</option>
          {PRODUCT_STATUS_OPTIONS.map(option => (
            <option key={option} value={option}>{option}</option>
          ))}
        </select>
        <button className="btn" onClick={onFilter}>Filter</button>
      </div>
      <span className="muted small">{itemCount} items</span>
    </div>
  )
}
