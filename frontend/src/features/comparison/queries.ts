import { useQuery } from '@tanstack/react-query'

import { qk } from '@/lib/queryKeys'

import { fetchRunComparison } from './api'

export function useRunComparison(runIds: string[]) {
  const sortedKey = [...runIds].sort().join(',')
  return useQuery({
    queryKey: qk.comparison.report(sortedKey),
    queryFn: () => fetchRunComparison(runIds),
    enabled: runIds.length >= 2,
  })
}
