type SkeletonProps = {
  width?: string
  height?: string
  className?: string
}

export function Skeleton({ width = '100%', height = '14px', className = '' }: SkeletonProps) {
  return <div className={`skeleton ${className}`.trim()} style={{ width, height }} aria-hidden="true" />
}
