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
        <input className="grow" placeholder="Titel*" {...register('title')} />
        <input placeholder="Brand" {...register('brand')} />
        <input placeholder="Model" {...register('model')} />
        <input placeholder="Wert (EUR)" {...register('currentValue')} />
      </div>

      {(errors.title || errors.currentValue) && (
        <div className="error mt8">{errors.title?.message || errors.currentValue?.message}</div>
      )}
    </form>
  )
}
