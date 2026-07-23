import { describe, expect, it } from 'vitest'
import { NAV_SECTIONS_TASK_BASED, routeLabel } from './navConfig'

describe('navConfig', () => {
  it('exposes the expected sections and route labels', () => {
    expect(NAV_SECTIONS_TASK_BASED).toHaveLength(4)
    expect(routeLabel('/dashboard')).toBe('Dashboard')
    expect(routeLabel('/products/123')).toBe('Produktdetail')
    expect(routeLabel('/deals')).toBe('E-Mail Threads')
    expect(routeLabel('/unknown')).toBe('Bereich')
  })
})
