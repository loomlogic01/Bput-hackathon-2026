import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'

import { ApiError, getCurrentUser, login as loginRequest } from '../api/client'
import type { CurrentUser } from '../api/client'

/** sessionStorage key holding the access token for this tab. */
const TOKEN_KEY = 'brsr.auth.token'

/**
 * sessionStorage is scoped to the tab and cleared when it closes, so the
 * session survives a refresh without persisting a credential to disk the way
 * localStorage would. Every access is guarded because storage can throw
 * (private browsing, disabled cookies, quota).
 */
function readStoredToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

function writeStoredToken(token: string): void {
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token)
  } catch {
    // Storage unavailable - the in-memory session still works for this tab.
  }
}

function clearStoredToken(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY)
  } catch {
    // Nothing to do; the in-memory state is cleared regardless.
  }
}

export interface AuthContextValue {
  /** The signed-in user, or null when signed out. */
  user: CurrentUser | null
  /** The JWT. Mirrored into sessionStorage so a refresh keeps the session. */
  token: string | null
  isAuthenticated: boolean
  /** True while a login request is in flight. */
  isLoading: boolean
  /** True while the stored token is being verified on startup. */
  isInitialising: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  // Starts true so the login page is not shown before a stored token has been
  // checked; App.tsx shows a placeholder until this settles.
  const [isInitialising, setIsInitialising] = useState(true)

  const logout = useCallback(() => {
    clearStoredToken()
    setToken(null)
    setUser(null)
  }, [])

  // On startup, restore a session from a token left in sessionStorage by a
  // previous page load. A token that no longer verifies is discarded.
  useEffect(() => {
    let cancelled = false

    async function restore() {
      const stored = readStoredToken()
      if (!stored) return

      try {
        const profile = await getCurrentUser(stored)
        if (cancelled) return
        setToken(stored)
        setUser(profile)
      } catch {
        // Expired, revoked or rejected - drop it and fall back to signed out.
        clearStoredToken()
        if (!cancelled) {
          setToken(null)
          setUser(null)
        }
      }
    }

    void restore().finally(() => {
      // Runs once the token check settles, including when there was no stored
      // token. Must not live in the cleanup below - that only runs on unmount.
      if (!cancelled) setIsInitialising(false)
    })

    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true)
    try {
      // 1. Exchange credentials for a token.
      const { access_token } = await loginRequest({ email, password })

      // 2. Resolve the profile with that token before treating the
      //    session as authenticated.
      const profile = await getCurrentUser(access_token)

      // 3. Persist only after the session is known to be good.
      writeStoredToken(access_token)
      setToken(access_token)
      setUser(profile)
    } catch (error) {
      // Never keep a half-built session.
      clearStoredToken()
      setToken(null)
      setUser(null)

      if (error instanceof ApiError) throw error
      throw new ApiError(0, 'Unable to reach the server. Is the backend running?')
    } finally {
      setIsLoading(false)
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isAuthenticated: token !== null && user !== null,
      isLoading,
      isInitialising,
      login,
      logout,
    }),
    [user, token, isLoading, isInitialising, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

/** Access the auth session. Must be used inside an <AuthProvider>. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an <AuthProvider>')
  }
  return context
}