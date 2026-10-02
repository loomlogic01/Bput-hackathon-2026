import { useEffect, useState } from 'react'

import type { BrsrFramework } from './api/client'
import { listFrameworks } from './api/client'
import { AuthProvider, useAuth } from './auth/AuthContext'
import LoginPage from './pages/LoginPage'
import './App.css'

/**
 * Minimal signed-in shell. The dashboard is not built yet - this only
 * confirms the session works end to end and offers a way back out.
 */
function SignedInView() {
  const { user, token, logout } = useAuth()
  const [frameworks, setFrameworks] = useState<BrsrFramework[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    listFrameworks(token)
      .then((data) => {
        if (!cancelled) setFrameworks(data)
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Request failed')
        }
      })
    return () => {
      cancelled = true
    }
  }, [token])

  return (
    <main className="app-shell">
      <section className="app-card">
        <header className="app-header">
          <div>
            <p className="app-eyebrow">SEBI BRSR</p>
            <h1 className="app-title">ESG &amp; Sustainability Portal</h1>
          </div>
          <button className="app-signout" type="button" onClick={logout}>
            Sign out
          </button>
        </header>

        <dl className="app-meta">
          <div>
            <dt>Signed in as</dt>
            <dd>{user?.full_name}</dd>
          </div>
          <div>
            <dt>Email</dt>
            <dd>{user?.email}</dd>
          </div>
          <div>
            <dt>Organisation</dt>
            <dd>{user?.organization_id ?? 'Not assigned'}</dd>
          </div>
        </dl>

        <div className="app-section">
          <h2 className="app-section-title">
            BRSR frameworks <span>(GET /brsr/)</span>
          </h2>
          {error && <p className="app-error">{error}</p>}
          {!frameworks && !error && <p className="app-muted">Loading…</p>}
          {frameworks && (
            <ul className="app-list">
              {frameworks.map((framework) => (
                <li key={framework.id}>
                  <strong>{framework.name}</strong>
                  <span className="app-badge">v{framework.version}</span>
                  <span className="app-muted">
                    {framework.description ?? '—'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <p className="app-hint">
          Dashboard coming next. Sign out to return to the login screen — the
          token is discarded from memory.
        </p>
      </section>
    </main>
  )
}

function App() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <SignedInView /> : <LoginPage />
}

export default function Root() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  )
}