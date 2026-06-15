export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export function apiAssetUrl(path: string) {
  if (!path.startsWith('/uploads/')) return path
  return `${API_BASE_URL}${path}`
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function errorMessage(response: Response, fallback: string) {
  try {
    const data = (await response.json()) as { detail?: unknown }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    return fallback
  }
  return fallback
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)

  if (!response.ok) {
    throw new ApiError(await errorMessage(response, `GET ${path} failed with ${response.status}`), response.status)
  }

  return response.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new ApiError(await errorMessage(response, `POST ${path} failed with ${response.status}`), response.status)
  }

  return response.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new ApiError(await errorMessage(response, `PATCH ${path} failed with ${response.status}`), response.status)
  }

  return response.json() as Promise<T>
}

export async function apiDelete<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new ApiError(await errorMessage(response, `DELETE ${path} failed with ${response.status}`), response.status)
  }

  return response.json() as Promise<T>
}

export async function apiUpload<T>(path: string, body: FormData, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: 'POST',
    body,
  })

  if (!response.ok) {
    throw new ApiError(await errorMessage(response, `POST ${path} failed with ${response.status}`), response.status)
  }

  return response.json() as Promise<T>
}
