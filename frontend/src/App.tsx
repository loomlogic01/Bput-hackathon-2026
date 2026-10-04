import { AuthProvider, useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'

function App() {
  const { isAuthenticated, isInitialising } = useAuth()

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

  return isAuthenticated ? <DashboardPage /> : <LoginPage />
}

export default function Root() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  )
}