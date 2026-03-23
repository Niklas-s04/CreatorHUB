import { Skeleton } from './Skeleton'

type ListSkeletonProps = {
  rows?: number
}

export function ListSkeleton({ rows = 5 }: ListSkeletonProps) {
  return (
    <div className="list-skeleton" role="status" aria-live="polite" aria-label="Liste wird geladen">
      {Array.from({ length: rows }).map((_, index) => (
        <div className="list-skeleton-row" key={index}>
          <Skeleton width="45%" height="14px" />
          <Skeleton width="20%" height="14px" />
          <Skeleton width="15%" height="14px" />
        </div>
      ))}
    </div>
  )
}
