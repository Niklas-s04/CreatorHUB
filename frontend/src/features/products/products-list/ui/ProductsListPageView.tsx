import React, { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { queryKeys } from '../../../../shared/api/queryKeys'
import { useCreateProductMutation, useProductsListQuery } from '../../../../shared/api/queries/products'
import type { ProductCreateFormValues } from '../../../../shared/forms/schemas'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { useAuthz } from '../../../../shared/hooks/useAuthz'
import { PageHeader } from '../../../../shared/ui/page/PageHeader'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'
import { ProductCreateForm } from './ProductCreateForm'
import { ProductsFilterBar } from './ProductsFilterBar'
import { ProductsTable } from './ProductsTable'

export default function ProductsListPageView() {
  const { hasPermission } = useAuthz()
  const toast = useToast()
  const [q, setQ] = useState('')
  const [status, setStatus] = useState('')
  const [appliedQ, setAppliedQ] = useState('')
  const [appliedStatus, setAppliedStatus] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [exportDataset, setExportDataset] = useState<'products' | 'transactions' | 'value_history'>('products')
  const [exportYears, setExportYears] = useState('')
  const queryClient = useQueryClient()

  const listParams = useMemo(() => ({ q: appliedQ || undefined, status: appliedStatus || undefined, limit: 100 }), [appliedQ, appliedStatus])
  const productsQuery = useProductsListQuery(listParams)
  const createMutation = useCreateProductMutation(listParams)

  const items = productsQuery.data ?? []

  async function load() {
    setAppliedQ(q)
    setAppliedStatus(status)
    setErr(null)
  }

  async function create(values: ProductCreateFormValues) {
    if (!hasPermission('product.write')) return
    try {
      setErr(null)
      const payload: { title: string; brand?: string; model?: string; current_value?: number } = { title: values.title.trim() }
      if (values.brand.trim()) payload.brand = values.brand.trim()
      if (values.model.trim()) payload.model = values.model.trim()
      if (values.currentValue.trim()) payload.current_value = Number(values.currentValue.replace(',', '.'))
      await createMutation.mutateAsync(payload)
      setShowNew(false)
      await queryClient.invalidateQueries({ queryKey: queryKeys.products.list(listParams) })
      toast.success('Produkt wurde gespeichert')
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
  }

  function handleExport() {
    if (!hasPermission('product.export')) return
    const params = new URLSearchParams()
    params.set('dataset', exportDataset)
    const yearTokens = exportYears
      .split(/[,\s]+/)
      .map(token => token.trim())
      .filter(Boolean)
    yearTokens.forEach(year => {
      const parsed = parseInt(year, 10)
      if (!Number.isNaN(parsed)) {
        params.append('years', String(parsed))
      }
    })
    const qs = params.toString()
    const url = `/api/products/export/csv${qs ? `?${qs}` : ''}`
    window.open(url, '_blank', 'noreferrer')
  }

  return (
    <div className="container">
      <PageHeader
        title="Inventar"
        subtitle="Produkte verwalten, filtern und exportieren."
        right={(
          <>
            <button className="btn primary" onClick={() => setShowNew(v => !v)} disabled={!hasPermission('product.write')}>
              {showNew ? 'Schließen' : '+ Produkt'}
            </button>
            <div className="control-row">
              <select value={exportDataset} onChange={e => setExportDataset(e.target.value as typeof exportDataset)}>
                <option value="products">Produkte</option>
                <option value="transactions">Transaktionen</option>
                <option value="value_history">Wert-Historie</option>
              </select>
              <input
                className="w180"
                placeholder="Jahre z.B. 2023,2024"
                value={exportYears}
                onChange={e => setExportYears(e.target.value)}
              />
              <button className="btn" onClick={handleExport} disabled={!hasPermission('product.export')}>
                Export CSV
              </button>
            </div>
          </>
        )}
      />

      {err && <ErrorState title="Aktion fehlgeschlagen" message={err} />}
      {productsQuery.error && !err && (
        <ErrorState
          title="Produkte konnten nicht geladen werden"
          message={getErrorMessage(productsQuery.error)}
          onRetry={() => {
            void productsQuery.refetch()
          }}
        />
      )}

      {showNew && (
        <ProductCreateForm
          canWrite={hasPermission('product.write')}
          isSubmitting={createMutation.isPending}
          onSave={create}
        />
      )}

      <div className="card section-gap">
        <ProductsFilterBar
          query={q}
          status={status}
          itemCount={items.length}
          onQueryChange={setQ}
          onStatusChange={setStatus}
          onFilter={load}
        />
        {productsQuery.isFetching && items.length === 0 ? (
          <ListSkeleton rows={6} />
        ) : (
          <ProductsTable items={items} />
        )}
      </div>
    </div>
  )
}