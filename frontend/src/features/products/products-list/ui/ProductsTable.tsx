import { Link } from 'react-router-dom'
import type { ProductListItemVm } from '../../../../shared/api/contracts'

export type ProductColumnKey =
  | 'title'
  | 'category'
  | 'condition'
  | 'status'
  | 'currentValue'
  | 'currency'

export type ProductSortField = 'title' | 'status' | 'current_value' | 'updated_at'

type ProductsTableProps = {
  items: ProductListItemVm[]
  visibleColumns: ProductColumnKey[]
  selectedIds: Set<string>
  sortBy: ProductSortField
  sortOrder: 'asc' | 'desc'
  onToggleRow: (id: string) => void
  onToggleAllRows: () => void
  onSort: (field: ProductSortField) => void
}

const COLUMN_LABELS: Record<ProductColumnKey, string> = {
  title: 'Titel',
  category: 'Kategorie',
  condition: 'Zustand',
  status: 'Status',
  currentValue: 'Wert',
  currency: 'Währung',
}

const SORTABLE_COLUMNS: Partial<Record<ProductColumnKey, ProductSortField>> = {
  title: 'title',
  status: 'status',
  currentValue: 'current_value',
}

export function ProductsTable({
  items,
  visibleColumns,
  selectedIds,
  sortBy,
  sortOrder,
  onToggleRow,
  onToggleAllRows,
  onSort,
}: ProductsTableProps) {
  const selectedOnPage = items.filter(item => selectedIds.has(String(item.id))).length
  const allSelected = items.length > 0 && selectedOnPage === items.length

  function sortIndicator(column: ProductColumnKey) {
    const field = SORTABLE_COLUMNS[column]
    if (!field) return null
    if (field !== sortBy) return <span className="muted small">↕</span>
    return <span className="muted small">{sortOrder === 'asc' ? '↑' : '↓'}</span>
  }

  function getSortAria(column: ProductColumnKey): 'none' | 'ascending' | 'descending' {
    const field = SORTABLE_COLUMNS[column]
    if (!field) return 'none'
    if (field !== sortBy) return 'none'
    return sortOrder === 'asc' ? 'ascending' : 'descending'
  }

  return (
    <table>
      <caption className="sr-only">Produktliste mit Auswahl und Sortierung</caption>
      <thead>
        <tr>
          <th scope="col">
            <input
              aria-label="Alle Produkte auf Seite auswählen"
              type="checkbox"
              checked={allSelected}
              onChange={onToggleAllRows}
            />
          </th>
          {visibleColumns.map(column => {
            const sortableField = SORTABLE_COLUMNS[column]
            return (
              <th key={column} scope="col" aria-sort={getSortAria(column)}>
                {sortableField ? (
                  <button
                    className="btn ghost"
                    type="button"
                    onClick={() => onSort(sortableField)}
                    aria-label={`${COLUMN_LABELS[column]} sortieren`}
                  >
                    {COLUMN_LABELS[column]} {sortIndicator(column)}
                  </button>
                ) : (
                  COLUMN_LABELS[column]
                )}
              </th>
            )
          })}
        </tr>
      </thead>
      <tbody>
        {items.map(product => (
          <tr key={product.id}>
            <td>
              <input
                aria-label={`Produkt ${product.title} auswählen`}
                type="checkbox"
                checked={selectedIds.has(String(product.id))}
                onChange={() => onToggleRow(String(product.id))}
              />
            </td>
            {visibleColumns.map(column => {
              if (column === 'title') {
                return (
                  <th key={`${product.id}-${column}`} scope="row">
                    <Link to={`/products/${product.id}`}>{product.title}</Link>
                  </th>
                )
              }
              if (column === 'category') return <td key={`${product.id}-${column}`}>{product.category}</td>
              if (column === 'condition') {
                return (
                  <td key={`${product.id}-${column}`}>
                    <span className="pill">{product.condition}</span>
                  </td>
                )
              }
              if (column === 'status') {
                return (
                  <td key={`${product.id}-${column}`}>
                    <span className="pill">{product.status}</span>
                  </td>
                )
              }
              if (column === 'currentValue') {
                return <td key={`${product.id}-${column}`}>{product.currentValue ?? ''}</td>
              }
              return <td key={`${product.id}-${column}`}>{product.currency}</td>
            })}
          </tr>
        ))}
        {!items.length && (
          <tr>
            <td colSpan={visibleColumns.length + 1} className="muted">Keine Treffer.</td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
