import { describe, expect, it } from 'vitest'
import { compareProjectsByDeadline, getProjectDeadline } from './projectDeadline'

const project = (
  id: string,
  title: string,
  due_date: string | null,
  preview_due_date: string | null
) => ({ id, title, due_date, preview_due_date })

describe('project deadlines', () => {
  it('uses the nearest due or review upload date', () => {
    expect(getProjectDeadline(project('1', 'Projekt', '2026-08-20', '2026-08-10'))).toBe(
      '2026-08-10'
    )
  })

  it('sorts the nearest deadline first and undated projects last', () => {
    const projects = [
      project('none', 'Ohne Termin', null, null),
      project('later', 'Später', '2026-08-20', null),
      project('review', 'Review', null, '2026-08-05'),
    ]

    expect(projects.sort(compareProjectsByDeadline).map(({ id }) => id)).toEqual([
      'review',
      'later',
      'none',
    ])
  })
})
