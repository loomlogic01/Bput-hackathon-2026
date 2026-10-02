import { AuthProvider, useAuth } from './auth/AuthContext'
import DashboardPage from './pages/DashboardPage'
import LoginPage from './pages/LoginPage'

function App() {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? <DashboardPage /> : <LoginPage />
}

export default function Root() {
  return (
    <AuthProvider>
      <App />
    </AuthProvider>
  )
}