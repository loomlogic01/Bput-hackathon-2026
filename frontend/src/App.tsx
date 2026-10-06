import { useState } from 'react'

import { AuthProvider, useAuth } from './auth/AuthContext'
import AuditLogPage from './pages/AuditLogPage'
import ConsolidationPage from './pages/ConsolidationPage'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'

type Page = 'dashboard' | 'consolidation' | 'audit'

function App() {
  const { isAuthenticated, isInitialising } = useAuth()
  const [page, setPage] = useState<Page>('dashboard')

  // Hold back both pages until a token left in sessionStorage has been
  // verified, otherwise a refresh flashes the login form before the restored
  // session replaces it.
  if (isInitialising) {
    return (
      <main className="auth-boot" role="status" aria-live="polite">
        Restoring session…
      </main>
    )
  }

  if (!isAuthenticated) return <LoginPage />

  if (page === 'consolidation') {
    return <ConsolidationPage onBack={() => setPage('dashboard')} />
  }

  if (page === 'audit') {
    return <AuditLogPage onBack={() => setPage('dashboard')} />
  }

  return <DashboardPage onNavigate={(p: Page) => setPage(p)} />
}

export default function Root() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  )
}