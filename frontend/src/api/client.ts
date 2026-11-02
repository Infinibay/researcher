/** Same-origin owner transport with explicit HTTP failures and encoded query values. @module */
import { ownerFetch } from './session.ts'

/** Preserve HTTP status so callers can distinguish rejection from an unavailable receipt. */
export class ApiError extends Error {
  status: number
  /** Keep the server explanation and response status without treating it as empty data. */
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

/** Fetch owner-authorized JSON; propagate non-success responses as errors. */
export async function fetchApi<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await ownerFetch(path, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = body.detail || body.message || body.error || message
    } catch {}
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

/** Encode optional filters as query values without changing the base endpoint. */
export function buildUrl(
  base: string,
  params?: Record<string, string | number | boolean | null | undefined>,
): string {
  if (!params) return base
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value != null && value !== '') {
      search.set(key, String(value))
    }
  }
  const qs = search.toString()
  return qs ? `${base}?${qs}` : base
}
