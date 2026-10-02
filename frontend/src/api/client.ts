/**
 * Minimal API client for the ESG/BRSR backend.
 *
 * Uses the browser's native fetch - no HTTP library (no axios, no ky).
 *
 * Authentication is deliberately NOT handled here yet: this module performs
 * no login and stores no token. A caller may pass a bearer token per request
 * via `options.token`, because most endpoints require one.
 */

/** Base URL of the backend, including the /api/v1 prefix. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

/** An HTTP error response from the backend. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** Serialised as JSON when provided. */
  body?: unknown
  /** Optional bearer token for this request only. Not stored. */
  token?: string
}

/** Perform a request against the backend and return the parsed JSON body. */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, token, headers, ...rest } = options

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  })

  if (!response.ok) {
    // FastAPI reports errors as { "detail": ... }; fall back to the status line.
    let detail = `${response.status} ${response.statusText}`
    try {
      const payload = await response.json()
      if (payload && typeof payload.detail === 'string') {
        detail = payload.detail
      }
    } catch {
      // Non-JSON error body - keep the status line.
    }
    throw new ApiError(response.status, detail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

// ── BRSR framework endpoints ──

export interface BrsrFramework {
  id: string
  name: string
  version: string
  description: string | null
  is_active: boolean
}

/** GET /brsr/ - all active BRSR frameworks. */
export function listFrameworks(token?: string): Promise<BrsrFramework[]> {
  return request<BrsrFramework[]>('/brsr/', { token })
}

// ── Authentication endpoints ──
// This module performs no token storage. The caller (AuthContext) owns the
// token and passes it per request.

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface CurrentUser {
  id: string
  email: string
  full_name: string
  is_active: boolean
  organization_id: string | null
  entity_id: string | null
  business_unit_id: string | null
  project_id: string | null
}

/** POST /auth/login - exchange credentials for a bearer token. */
export function login(credentials: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: credentials,
  })
}

/** GET /auth/me - resolve the signed-in user from a bearer token. */
export function getCurrentUser(token: string): Promise<CurrentUser> {
  return request<CurrentUser>('/auth/me', { token })
}