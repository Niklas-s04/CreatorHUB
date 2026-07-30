import type { Project } from './model'

type ProjectDeadline = Pick<Project, 'due_date' | 'preview_due_date'>
type ProjectDeadlineSort = ProjectDeadline & Pick<Project, 'id' | 'title'>

function timestamp(value: string | null): number | null {
  if (!value) return null
  const parsed = Date.parse(value)
  return Number.isNaN(parsed) ? null : parsed
}

export function getProjectDeadline(project: ProjectDeadline): string | null {
  const deadlines = [project.due_date, project.preview_due_date]
    .map((value) => ({ value, timestamp: timestamp(value) }))
    .filter(
      (deadline): deadline is { value: string; timestamp: number } =>
        deadline.value !== null && deadline.timestamp !== null
    )
    .sort((left, right) => left.timestamp - right.timestamp)

  return deadlines[0]?.value ?? null
}

export function compareProjectsByDeadline(
  left: ProjectDeadlineSort,
  right: ProjectDeadlineSort
): number {
  const leftDeadline = timestamp(getProjectDeadline(left))
  const rightDeadline = timestamp(getProjectDeadline(right))

  if (leftDeadline === null && rightDeadline !== null) return 1
  if (leftDeadline !== null && rightDeadline === null) return -1
  if (leftDeadline !== null && rightDeadline !== null && leftDeadline !== rightDeadline) {
    return leftDeadline - rightDeadline
  }

  const titleOrder = left.title.localeCompare(right.title, 'de-DE')
  return titleOrder || left.id.localeCompare(right.id)
}
