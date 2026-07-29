import { useQuery } from '@tanstack/react-query'

import { fetchHealth } from '@/features/system/api'
import { qk } from '@/lib/queryKeys'

export function useHealth() {
  return useQuery({
    queryKey: qk.system.health(),
    queryFn: fetchHealth,
    staleTime: 10_000,
  })
}
