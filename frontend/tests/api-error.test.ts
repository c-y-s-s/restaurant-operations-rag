import { describe, expect, it } from 'vitest'
import { getApiErrorMessage } from '../utils/api-error'

describe('getApiErrorMessage', () => {
  it('prefers the API detail', () => {
    expect(getApiErrorMessage({ data: { detail: 'Daily limit reached' } }))
      .toBe('Daily limit reached')
  })

  it('falls back to a friendly message', () => {
    expect(getApiErrorMessage(null)).toContain('無法連線')
  })

  it('does not expose low-level fetch errors', () => {
    expect(getApiErrorMessage({ message: '[POST] failed to fetch' }))
      .toBe('目前無法連線到知識服務，請稍後再試。')
  })
})
