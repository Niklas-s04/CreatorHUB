import { Link } from 'react-router-dom'
import type { ProductListItemVm } from '../../../../shared/api/contracts'

type ProductsTableProps = {
  items: ProductListItemVm[]
}

export function ProductsTable({ items }: ProductsTableProps) {
  return (
    <table>
      <thead>
        <tr>
          <th>Titel</th>
          <th>Kategorie</th>
          <th>Zustand</th>
          <th>Status</th>
          <th>Wert</th>
        </tr>
      </thead>
      <tbody>
        {items.map(product => (
          <tr key={product.id}>
            <td><Link to={`/products/${product.id}`}>{product.title}</Link></td>
            <td>{product.category}</td>
            <td><span className="pill">{product.condition}</span></td>
            <td><span className="pill">{product.status}</span></td>
            <td>{product.currentValue ?? ''} {product.currency}</td>
          </tr>
        ))}
        {!items.length && (
          <tr>
            <td colSpan={5} className="muted">Keine Treffer.</td>
          </tr>
        )}
      </tbody>
    </table>
  )
}
