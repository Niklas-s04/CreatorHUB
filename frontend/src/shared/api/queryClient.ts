import { QueryClient } from '@tanstack/react-query'
import { ApiError } from './httpClient'

function shouldRetry(failureCount: number, error: unknown) {
  if (failureCount >= 2) return false
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403 || error.status === 404) return false
    return error.status === 408 || error.status === 429 || error.status >= 500
  }
  return true
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: false,
      retry: shouldRetry,
      retryDelay: attempt => Math.min(300 * 2 ** attempt, 3_000),
    },
    mutations: {
      retry: 0,
    },
  },
})
