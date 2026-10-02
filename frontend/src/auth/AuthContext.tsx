import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'

import { ApiError, getCurrentUser, login as loginRequest } from '../api/client'
import type { CurrentUser } from '../api/client'

export interface AuthContextValue {
  /** The signed-in user, or null when signed out. */
  user: CurrentUser | null
  /** The JWT. Lives in this React state only - never written to storage. */
  token: string | null
  isAuthenticated: boolean
  /** True while a login request is in flight. */
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  // The token is deliberately held in memory only. Using localStorage,
  // sessionStorage or a cookie would leave a credential on disk and make the
  // session survive a reload, which this design intentionally avoids.
  const [token, setToken] = useState<string | null>(null)
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true)
    try {
      // 1. Exchange credentials for a token.
      const { access_token } = await loginRequest({ email, password })

      // 2. Resolve the profile with that token before treating the
      //    session as authenticated.
      const profile = await getCurrentUser(access_token)

      setToken(access_token)
      setUser(profile)
    } catch (error) {
      // Never keep a half-built session.
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
      login,
      logout,
    }),
    [user, token, isLoading, login, logout],
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