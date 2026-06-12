const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init)

  if (!response.ok) {
    throw new ApiError(`GET ${path} failed with ${response.status}`, response.status)
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
    throw new ApiError(`POST ${path} failed with ${response.status}`, response.status)
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
    throw new ApiError(`PATCH ${path} failed with ${response.status}`, response.status)
  }

  return response.json() as Promise<T>
}

export async function apiDelete<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new ApiError(`DELETE ${path} failed with ${response.status}`, response.status)
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
    throw new ApiError(`POST ${path} failed with ${response.status}`, response.status)
  }

  return response.json() as Promise<T>
}
