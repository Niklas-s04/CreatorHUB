import { describe, expect, it } from 'vitest'
import { queryKeys } from './queryKeys'

describe('queryKeys', () => {
  it('builds stable tuple keys', () => {
    expect(queryKeys.auth.me()).toEqual(['auth', 'me'])
    expect(queryKeys.products.detail('1')).toEqual(['products', 'detail', '1'])
    expect(queryKeys.admin.registrationRequests('pending')).toEqual([
      'admin',
      'registrationRequests',
      'pending',
    ])
  })
})
