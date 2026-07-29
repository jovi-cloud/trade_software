import { api } from '@/lib/apiClient'

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  database: 'ok' | 'error'
}

export function fetchHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>('/system/health')
}
