import { useAuthStore } from '../stores/auth'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export class ApiError extends Error {
  status: number
  body: Record<string, unknown>

  constructor(status: number, body: Record<string, unknown>) {
    super((body?.detail as string) || (body?.message as string) || `HTTP ${status}`)
    this.status = status
    this.body = body
  }
}

async function request<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const auth = useAuthStore()
  const headers = new Headers(options.headers)

  if (auth.token) {
    headers.set('Authorization', `Bearer ${auth.token}`)
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })

  if (!res.ok) {
    let body: Record<string, unknown>
    try {
      body = await res.json()
    } catch {
      body = { detail: res.statusText }
    }
    throw new ApiError(res.status, body)
  }

  if (res.status === 204) return null as T
  return res.json() as Promise<T>
}

export function useApi() {
  return {
    get: <T = unknown>(path: string) => request<T>(path),

    post: <T = unknown>(path: string, body: unknown) =>
      request<T>(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      }),

    postForm: <T = unknown>(path: string, data: Record<string, string>) => {
      const params = new URLSearchParams()
      for (const [key, value] of Object.entries(data)) {
        params.append(key, value)
      }
      return request<T>(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params,
      })
    },
  }
}
