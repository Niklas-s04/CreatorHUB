import React, { useMemo, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { apiFetch } from '../../../../api'
import { toProductDetailVm } from '../../../../shared/api/mappers'
import { queryKeys } from '../../../../shared/api/queryKeys'
import { parseProductDto } from '../../../../shared/api/validators'
import { useCreateProductMutation, useProductsListQuery } from '../../../../shared/api/queries/products'
import type { ProductCreateFormValues } from '../../../../shared/forms/schemas'
import { useDebouncedValue } from '../../../../shared/hooks/useDebouncedValue'
import { getErrorMessage } from '../../../../shared/lib/errors'
import { useAuthz } from '../../../../shared/hooks/useAuthz'
import { PageHeader } from '../../../../shared/ui/page/PageHeader'
import { ErrorState } from '../../../../shared/ui/states/ErrorState'
import { ListSkeleton } from '../../../../shared/ui/states/ListSkeleton'
import { useToast } from '../../../../shared/ui/toast/ToastProvider'
import { ProductCreateForm } from './ProductCreateForm'
import { ProductsFilterBar } from './ProductsFilterBar'
import { type ProductColumnKey, type ProductSortField, ProductsTable } from './ProductsTable'

const SAVED_VIEWS_KEY = 'products.savedViews.v1'
const COLUMNS_KEY = 'products.columns.v1'

const DEFAULT_COLUMNS: ProductColumnKey[] = [
  'title',
  'category',
  'condition',
  'status',
  'currentValue',
  'currency',
]

const ALL_COLUMNS: { key: ProductColumnKey; label: string }[] = [
  { key: 'title', label: 'Titel' },
  { key: 'category', label: 'Kategorie' },
  { key: 'condition', label: 'Zustand' },
  { key: 'status', label: 'Status' },
  { key: 'currentValue', label: 'Wert' },
  { key: 'currency', label: 'Währung' },
]

type SavedView = {
  id: string
  name: string
  q: string
  status: string
  limit: number
  sortBy: ProductSortField
  sortOrder: 'asc' | 'desc'
  columns: ProductColumnKey[]
}

function parsePositiveInt(value: string | null, fallback: number): number {
  const parsed = Number.parseInt(value || '', 10)
  const normalized = Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
  return Math.min(60, normalized)
}

function parseOffset(value: string | null): number {
  const parsed = Number.parseInt(value || '', 10)
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0
}

function parseSortBy(value: string | null): ProductSortField {
  if (value === 'title' || value === 'status' || value === 'current_value' || value === 'updated_at') {
    return value
  }
  return 'updated_at'
}

function parseSortOrder(value: string | null): 'asc' | 'desc' {
  return value === 'asc' ? 'asc' : 'desc'
}

function parseColumns(value: string | null): ProductColumnKey[] {
  if (!value) return []
  const entries = value
    .split(',')
    .map(token => token.trim())
    .filter((token): token is ProductColumnKey =>
      ['title', 'category', 'condition', 'status', 'currentValue', 'currency'].includes(token)
    )
  return Array.from(new Set(entries))
}

function loadColumnsFromStorage(): ProductColumnKey[] {
  try {
    const raw = localStorage.getItem(COLUMNS_KEY)
    if (!raw) return DEFAULT_COLUMNS
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return DEFAULT_COLUMNS
    const cols = parsed.filter((entry): entry is ProductColumnKey =>
      ['title', 'category', 'condition', 'status', 'currentValue', 'currency'].includes(String(entry))
    )
    return cols.length ? cols : DEFAULT_COLUMNS
  } catch {
    return DEFAULT_COLUMNS
  }
}

function loadSavedViews(): SavedView[] {
  try {
    const raw = localStorage.getItem(SAVED_VIEWS_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed
      .map(entry => {
        if (!entry || typeof entry !== 'object') return null
        const view = entry as Partial<SavedView>
        if (!view.id || !view.name) return null
        return {
          id: String(view.id),
          name: String(view.name),
          q: String(view.q || ''),
          status: String(view.status || ''),
          limit: parsePositiveInt(String(view.limit || ''), 50),
          sortBy: parseSortBy(String(view.sortBy || 'updated_at')),
          sortOrder: parseSortOrder(String(view.sortOrder || 'desc')),
          columns: Array.from(new Set(view.columns || [])).filter((token): token is ProductColumnKey =>
            ['title', 'category', 'condition', 'status', 'currentValue', 'currency'].includes(String(token))
          ),
        }
      })
      .filter((view): view is SavedView => Boolean(view))
  } catch {
    return []
  }
}

function persistSavedViews(views: SavedView[]) {
  localStorage.setItem(SAVED_VIEWS_KEY, JSON.stringify(views))
}

export default function ProductsListPageView() {
  const { hasPermission } = useAuthz()
  const toast = useToast()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlQ = searchParams.get('q') || ''
  const urlStatus = searchParams.get('status') || ''
  const urlLimit = parsePositiveInt(searchParams.get('limit'), 50)
  const urlOffset = parseOffset(searchParams.get('offset'))
  const urlSortBy = parseSortBy(searchParams.get('sort_by'))
  const urlSortOrder = parseSortOrder(searchParams.get('sort_order'))

  const [q, setQ] = useState(urlQ)
  const [status, setStatus] = useState(urlStatus)
  const debouncedQ = useDebouncedValue(q, 350)
  const debouncedStatus = useDebouncedValue(status, 350)
  const [err, setErr] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [savedViews, setSavedViews] = useState<SavedView[]>(() => loadSavedViews())
  const [newViewName, setNewViewName] = useState('')

  const initialColumns = useMemo(() => {
    const fromUrl = parseColumns(searchParams.get('cols'))
    if (fromUrl.length) return fromUrl
    return loadColumnsFromStorage()
  }, [])
  const [visibleColumns, setVisibleColumns] = useState<ProductColumnKey[]>(initialColumns)
  const [tableInteractionVersion, setTableInteractionVersion] = useState(0)

  const [exportDataset, setExportDataset] = useState<'products' | 'transactions' | 'value_history'>('products')
  const [exportYears, setExportYears] = useState('')
  const queryClient = useQueryClient()

  const listParams = useMemo(
    () => ({
      q: urlQ || undefined,
      status: urlStatus || undefined,
      limit: urlLimit,
      offset: urlOffset,
      sort_by: urlSortBy,
      sort_order: urlSortOrder,
    }),
    [urlQ, urlStatus, urlLimit, urlOffset, urlSortBy, urlSortOrder]
  )
  const productsQuery = useProductsListQuery(listParams)

  React.useEffect(() => {
    const normalizedQ = debouncedQ.trim()
    if (normalizedQ === urlQ && debouncedStatus === urlStatus) return
    updateParams({
      q: normalizedQ || null,
      status: debouncedStatus || null,
      offset: '0',
    })
    setSelectedIds(new Set())
  }, [debouncedQ, debouncedStatus, urlQ, urlStatus])

  React.useEffect(() => {
    const table = document.getElementById('products-table-anchor')
    if (!table || tableInteractionVersion === 0) return
    table.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [tableInteractionVersion])

  const createMutation = useCreateProductMutation(listParams)

  const items = productsQuery.data?.items ?? []
  const meta = productsQuery.data?.meta ?? {
    limit: urlLimit,
    offset: urlOffset,
    total: items.length,
    sort_by: urlSortBy,
    sort_order: urlSortOrder,
  }

  function updateParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (value === null || value === '') next.delete(key)
      else next.set(key, value)
    })
    setSearchParams(next, { replace: true })
  }

  async function load() {
    updateParams({
      q: q.trim() || null,
      status: status || null,
      offset: '0',
    })
    setSelectedIds(new Set())
    setErr(null)
  }

  function resetFilters() {
    setQ('')
    setStatus('')
    updateParams({
      q: null,
      status: null,
      offset: '0',
      sort_by: 'updated_at',
      sort_order: 'desc',
    })
    setSelectedIds(new Set())
  }

  function setPageSize(limit: number) {
    updateParams({ limit: String(limit), offset: '0' })
    setSelectedIds(new Set())
  }

  function changePage(direction: 'prev' | 'next') {
    const nextOffset = direction === 'prev' ? Math.max(0, meta.offset - meta.limit) : meta.offset + meta.limit
    updateParams({ offset: String(nextOffset) })
    setSelectedIds(new Set())
    setTableInteractionVersion(value => value + 1)
  }

  function handleSort(field: ProductSortField) {
    const nextOrder = meta.sort_by === field && meta.sort_order === 'desc' ? 'asc' : 'desc'
    updateParams({ sort_by: field, sort_order: nextOrder, offset: '0' })
    setSelectedIds(new Set())
    setTableInteractionVersion(value => value + 1)
  }

  function prefetchProductDetail(id: string) {
    void queryClient.prefetchQuery({
      queryKey: queryKeys.products.detail(id),
      queryFn: async () => {
        const data = await apiFetch<unknown>(`/products/${id}`)
        return toProductDetailVm(parseProductDto(data))
      },
      staleTime: 20_000,
    })
  }

  function toggleColumn(column: ProductColumnKey) {
    setVisibleColumns(current => {
      const exists = current.includes(column)
      const next = exists ? current.filter(item => item !== column) : [...current, column]
      if (next.length === 0) return current
      localStorage.setItem(COLUMNS_KEY, JSON.stringify(next))
      updateParams({ cols: next.join(',') })
      return next
    })
  }

  function toggleRowSelection(id: string) {
    setSelectedIds(current => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleAllOnPage() {
    const idsOnPage = items.map(item => String(item.id))
    const allSelected = idsOnPage.length > 0 && idsOnPage.every(id => selectedIds.has(id))
    setSelectedIds(current => {
      const next = new Set(current)
      if (allSelected) {
        idsOnPage.forEach(id => next.delete(id))
      } else {
        idsOnPage.forEach(id => next.add(id))
      }
      return next
    })
  }

  async function bulkArchiveSelection() {
    if (!selectedIds.size || !hasPermission('product.write')) return
    try {
      setErr(null)
      const today = new Date().toISOString().slice(0, 10)
      await Promise.all(
        Array.from(selectedIds).map(id =>
          apiFetch(`/products/${id}/status`, {
            method: 'POST',
            body: JSON.stringify({ status: 'archived', date: today, amount: null }),
          })
        )
      )
      setSelectedIds(new Set())
      await queryClient.invalidateQueries({ queryKey: ['products', 'list'] })
      toast.success('Ausgewählte Produkte wurden archiviert')
    } catch (e: unknown) {
      const message = getErrorMessage(e)
      setErr(message)
      toast.error(message)
    }
  }

  function saveView() {
    const name = newViewName.trim()
    if (!name) return
    const view: SavedView = {
      id: `${Date.now()}`,
      name,
      q: q.trim(),
      status,
      limit: meta.limit,
      sortBy: parseSortBy(meta.sort_by),
      sortOrder: meta.sort_order,
      columns: visibleColumns,
    }
    const next = [view, ...savedViews].slice(0, 20)
    setSavedViews(next)
    persistSavedViews(next)
    setNewViewName('')
    toast.success('Ansicht gespeichert')
  }

  function applyView(viewId: string) {
    const view = savedViews.find(entry => entry.id === viewId)
    if (!view) return
    setQ(view.q)
    setStatus(view.status)
    setVisibleColumns(view.columns.length ? view.columns : DEFAULT_COLUMNS)
    localStorage.setItem(COLUMNS_KEY, JSON.stringify(view.columns.length ? view.columns : DEFAULT_COLUMNS))
    updateParams({
      q: view.q || null,
      status: view.status || null,
      limit: String(view.limit),
      offset: '0',
      sort_by: view.sortBy,
      sort_order: view.sortOrder,
      cols: (view.columns.length ? view.columns : DEFAULT_COLUMNS).join(','),
    })
    setSelectedIds(new Set())
  }

  function deleteView(viewId: string) {
    const next = savedViews.filter(entry => entry.id !== viewId)
    setSavedViews(next)
    persistSavedViews(next)
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
    if (exportDataset === 'products') {
      if (urlQ) params.set('q', urlQ)
      if (urlStatus) params.set('status', urlStatus)
      params.set('sort_by', meta.sort_by)
      params.set('sort_order', meta.sort_order)
    }
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
              <label className="sr-only" htmlFor="products-export-dataset">Export-Datensatz</label>
              <select id="products-export-dataset" value={exportDataset} onChange={e => setExportDataset(e.target.value as typeof exportDataset)}>
                <option value="products">Produkte</option>
                <option value="transactions">Transaktionen</option>
                <option value="value_history">Wert-Historie</option>
              </select>
              <label className="sr-only" htmlFor="products-export-years">Export-Jahre</label>
              <input
                id="products-export-years"
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
        <div id="products-table-anchor" />
        <ProductsFilterBar
          query={q}
          status={status}
          pageSize={meta.limit}
          total={meta.total}
          offset={meta.offset}
          itemCount={items.length}
          onQueryChange={setQ}
          onStatusChange={setStatus}
          onPageSizeChange={setPageSize}
          onFilter={load}
          onReset={resetFilters}
          extraActions={(
            <div className="control-row">
              <label className="sr-only" htmlFor="products-view-name">Name für gespeicherte Ansicht</label>
              <input
                id="products-view-name"
                className="w180"
                placeholder="Ansicht speichern…"
                value={newViewName}
                onChange={e => setNewViewName(e.target.value)}
              />
              <button className="btn" onClick={saveView}>View speichern</button>
              <label className="sr-only" htmlFor="products-saved-views">Gespeicherte Ansichten</label>
              <select id="products-saved-views" onChange={e => applyView(e.target.value)} value="">
                <option value="">Gespeicherte Ansichten…</option>
                {savedViews.map(view => (
                  <option key={view.id} value={view.id}>{view.name}</option>
                ))}
              </select>
              <details>
                <summary className="btn ghost" aria-label="Spaltenauswahl öffnen">Spalten</summary>
                <div className="card stack">
                  {ALL_COLUMNS.map(column => (
                    <label key={column.key} className="small">
                      <input
                        type="checkbox"
                        checked={visibleColumns.includes(column.key)}
                        onChange={() => toggleColumn(column.key)}
                      />{' '}
                      {column.label}
                    </label>
                  ))}
                </div>
              </details>
            </div>
          )}
        />
        {!!selectedIds.size && (
          <div className="row between section-gap">
            <span className="muted small">{selectedIds.size} ausgewählt</span>
            <div className="control-row">
              <button className="btn danger" onClick={() => void bulkArchiveSelection()} disabled={!hasPermission('product.write')}>
                Bulk: Archivieren
              </button>
              <button className="btn ghost" onClick={() => setSelectedIds(new Set())}>Auswahl löschen</button>
            </div>
          </div>
        )}
        {productsQuery.isFetching && items.length === 0 ? (
          <ListSkeleton rows={6} />
        ) : (
          <ProductsTable
            items={items}
            visibleColumns={visibleColumns}
            selectedIds={selectedIds}
            sortBy={parseSortBy(meta.sort_by)}
            sortOrder={meta.sort_order}
            onToggleRow={toggleRowSelection}
            onToggleAllRows={toggleAllOnPage}
            onSort={handleSort}
            onPrefetchDetail={prefetchProductDetail}
          />
        )}
        <div className="row between mt8">
          <button className="btn" onClick={() => changePage('prev')} disabled={meta.offset <= 0}>← Zurück</button>
          <span className="muted small">Offset {meta.offset} · Limit {meta.limit} · Gesamt {meta.total}</span>
          <button
            className="btn"
            onClick={() => changePage('next')}
            disabled={meta.offset + meta.limit >= meta.total}
          >
            Weiter →
          </button>
        </div>
        {!!savedViews.length && (
          <div className="control-row mt8">
            {savedViews.map(view => (
              <button key={view.id} className="btn ghost" onClick={() => deleteView(view.id)}>
                View löschen: {view.name}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}