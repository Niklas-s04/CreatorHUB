import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import type { ProductCreateFormValues } from '../../../../shared/forms/schemas'
import { productCreateSchema } from '../../../../shared/forms/schemas'

type ProductCreateFormProps = {
  canWrite: boolean
  isSubmitting: boolean
  onSave: (values: ProductCreateFormValues) => Promise<void>
}

export function ProductCreateForm({
  canWrite,
  isSubmitting,
  onSave,
}: ProductCreateFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProductCreateFormValues>({
    resolver: zodResolver(productCreateSchema),
    mode: 'onChange',
    defaultValues: {
      title: '',
      brand: '',
      model: '',
      currentValue: '',
    },
  })

  async function submit(values: ProductCreateFormValues) {
    await onSave(values)
    reset()
  }

  return (
    <form className="card section-gap" onSubmit={handleSubmit(submit)}>
      <div className="page-header no-margin">
        <h3>Neues Produkt</h3>
        <button
          className="btn"
          type="submit"
          disabled={!canWrite || !isDirty || Boolean(errors.title) || Boolean(errors.currentValue) || isSubmitting}
        >
          {isSubmitting ? 'Speichern…' : 'Speichern'}
        </button>
      </div>

      <div className="control-row section-gap">
        <label className="sr-only" htmlFor="product-create-title">Titel</label>
        <input
          id="product-create-title"
          className="grow"
          placeholder="Titel*"
          {...register('title')}
          aria-invalid={Boolean(errors.title)}
          aria-describedby={errors.title ? 'product-create-title-error' : undefined}
        />
        <label className="sr-only" htmlFor="product-create-brand">Brand</label>
        <input id="product-create-brand" placeholder="Brand" {...register('brand')} />
        <label className="sr-only" htmlFor="product-create-model">Model</label>
        <input id="product-create-model" placeholder="Model" {...register('model')} />
        <label className="sr-only" htmlFor="product-create-current-value">Wert (EUR)</label>
        <input
          id="product-create-current-value"
          placeholder="Wert (EUR)"
          {...register('currentValue')}
          aria-invalid={Boolean(errors.currentValue)}
          aria-describedby={errors.currentValue ? 'product-create-current-value-error' : undefined}
        />
      </div>

      {(errors.title || errors.currentValue) && (
        <div className="error mt8" role="alert">
          {errors.title?.message && <span id="product-create-title-error">{errors.title.message}</span>}
          {errors.currentValue?.message && <span id="product-create-current-value-error">{errors.currentValue.message}</span>}
        </div>
      )}
    </form>
  )
}
