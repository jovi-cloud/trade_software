/**
 * The single place the frontend talks to the backend.
 *
 * Normalises the API's `{ error: { code, message } }` shape into a thrown
 * ApiError, so every query hook can rely on `error.code` being present.
 */

const API_BASE = '/api/v1'

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details?: unknown
  }
}

export class ApiError extends Error {
  readonly code: string
  readonly status: number
  readonly details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const { error } = value as { error: unknown }
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown
  /** Query string parameters; undefined and null values are dropped. */
  params?: Record<string, string | number | boolean | undefined | null>
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const url = `${API_BASE}${path}`
  if (!params) return url

  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) search.append(key, String(value))
  }
  const query = search.toString()
  return query ? `${url}?${query}` : url
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, params, headers, ...rest } = options

  // FormData must be passed through untouched: the browser sets the
  // multipart Content-Type with its own boundary, and setting it here
  // manually would produce a body the server cannot parse.
  const isFormData = body instanceof FormData

  const response = await fetch(buildUrl(path, params), {
    ...rest,
    headers: {
      ...(body === undefined || isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    ...(body === undefined ? {} : { body: isFormData ? body : JSON.stringify(body) }),
  })

  if (response.status === 204) return undefined as T

  const payload: unknown = await response.json().catch(() => null)

  if (!response.ok) {
    if (isApiErrorBody(payload)) {
      throw new ApiError(
        response.status,
        payload.error.code,
        payload.error.message,
        payload.error.details,
      )
    }
    throw new ApiError(response.status, 'UNKNOWN_ERROR', response.statusText || 'Request failed')
  }

  return payload as T
}

/** Normalises any thrown error into a message safe to show a user. */
export function getErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (error instanceof ApiError) return error.message
  if (error instanceof Error) return error.message
  return fallback
}

export const api = {
  get: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, options?: RequestOptions) =>
    apiRequest<T>(path, { ...options, method: 'DELETE' }),
}
