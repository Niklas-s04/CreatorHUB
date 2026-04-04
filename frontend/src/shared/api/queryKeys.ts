export const queryKeys = {
  auth: {
    me: () => ['auth', 'me'] as const,
    sessions: () => ['auth', 'sessions'] as const,
    loginHistory: (limit: number) => ['auth', 'loginHistory', limit] as const,
    users: () => ['auth', 'users'] as const,
  },
  products: {
    list: (params: {
      q?: string
      status?: string
      limit?: number
      offset?: number
      sort_by?: string
      sort_order?: 'asc' | 'desc'
    }) => ['products', 'list', params] as const,
    detail: (id: string) => ['products', 'detail', id] as const,
    transactions: (id: string) => ['products', 'transactions', id] as const,
    assets: (id: string) => ['products', 'assets', id] as const,
  },
  content: {
    tasks: () => ['content', 'tasks'] as const,
  },
  knowledge: {
    docs: () => ['knowledge', 'docs'] as const,
    rateCard: () => ['knowledge', 'rateCard'] as const,
  },
  assets: {
    library: (params: Record<string, string>) => ['assets', 'library', params] as const,
    thumb: (id: string) => ['assets', 'thumb', id] as const,
  },
  email: {
    threads: (limit: number) => ['email', 'threads', limit] as const,
    thread: (id: string) => ['email', 'thread', id] as const,
  },
  admin: {
    registrationRequests: (statusFilter: 'pending' | 'approved' | 'rejected') => ['admin', 'registrationRequests', statusFilter] as const,
    registrationRequestsAll: () => ['admin', 'registrationRequests', 'all'] as const,
    userSessions: (userId: string) => ['admin', 'userSessions', userId] as const,
  },
}
