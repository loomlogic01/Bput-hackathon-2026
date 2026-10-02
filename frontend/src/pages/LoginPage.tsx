import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './LoginPage.css'

export default function LoginPage() {
  const { login, isLoading } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (isLoading) return
    setError(null)

    try {
      await login(email.trim(), password)
      setPassword('')
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError('Invalid email or password.')
        } else if (err.status === 0) {
          setError('Cannot reach the server. Is the backend running?')
        } else {
          setError(err.message)
        }
      } else {
        setError('Something went wrong. Please try again.')
      }
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <header className="login-header">
          <p className="login-eyebrow">SEBI BRSR</p>
          <h1 className="login-title">ESG &amp; Sustainability Portal</h1>
          <p className="login-subtitle">
            Sign in to prepare and review your BRSR disclosures.
          </p>
        </header>

        <form className="login-form" onSubmit={handleSubmit} noValidate>
          {error && (
            <p className="login-error" role="alert">
              {error}
            </p>
          )}

          <div className="field">
            <label className="field-label" htmlFor="email">
              Email address
            </label>
            <input
              className="field-input"
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="field">
            <label className="field-label" htmlFor="password">
              Password
            </label>
            <input
              className="field-input"
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={isLoading}
            />
          </div>

          <button className="login-submit" type="submit" disabled={isLoading}>
            {isLoading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <footer className="login-footer">
          <span className="login-dot" aria-hidden="true" />
          Access is restricted to authorised reporting personnel.
        </footer>
      </section>
    </main>
  )
}