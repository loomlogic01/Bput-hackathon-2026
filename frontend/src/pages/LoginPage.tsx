import { useState } from 'react'
import type { FormEvent } from 'react'
import { Eye, EyeOff, Lock, Mail, ShieldCheck, Leaf, CheckCircle2 } from 'lucide-react'

import { ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './LoginPage.css'

export default function LoginPage() {
  const { login, isLoading } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
      <div className="login-backdrop-glow" aria-hidden="true" />
      
      <div className="login-container">
        {/* Left Side: Brand Narrative & Compliance Pillar */}
        <section className="login-hero-panel">
          <div className="login-hero-brand">
            <div className="login-hero-logo">
              <Leaf className="login-hero-logo-icon" />
            </div>
            <div>
              <span className="login-hero-badge">SEBI Compliant</span>
              <h2 className="login-hero-heading">Business Responsibility &amp; Sustainability Portal</h2>
            </div>
          </div>

          <p className="login-hero-lead">
            Standardised digital reporting architecture aligned with SEBI circular 
            guidelines for BRSR Core and comprehensive ESG compliance.
          </p>

          <div className="login-features">
            <div className="login-feature-item">
              <div className="login-feature-icon-box">
                <CheckCircle2 size={16} />
              </div>
              <div>
                <strong className="login-feature-title">Audited Disclosures</strong>
                <p className="login-feature-desc">Nine principles of National Guidelines on Responsible Business Conduct.</p>
              </div>
            </div>

            <div className="login-feature-item">
              <div className="login-feature-icon-box">
                <ShieldCheck size={16} />
              </div>
              <div>
                <strong className="login-feature-title">Multi-Tier Governance</strong>
                <p className="login-feature-desc">Integrated workflow for Preparers, Reviewers, and Approver sign-off.</p>
              </div>
            </div>
          </div>

          <div className="login-hero-footer">
            <span className="login-indicator-dot" />
            <span>Secure Enterprise Node · 256-bit Tokenized Authentication</span>
          </div>
        </section>

        {/* Right Side: Sign-in Form Card */}
        <section className="login-card">
          <header className="login-header">
            <div className="login-mobile-logo">
              <Leaf className="login-mobile-icon" size={20} />
              <span>SEBI BRSR</span>
            </div>
            <h1 className="login-title">Sign in to your account</h1>
            <p className="login-subtitle">
              Enter your corporate credentials to access reporting dashboards
            </p>
          </header>

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            {error && (
              <div className="login-error" role="alert">
                <div className="login-error-dot" />
                <span>{error}</span>
              </div>
            )}

            <div className="field">
              <label className="field-label" htmlFor="email">
                Email address
              </label>
              <div className="field-input-wrap">
                <Mail className="field-icon" size={17} />
                <input
                  className="field-input with-left-icon"
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="username"
                  placeholder="name@company.com"
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={isLoading}
                />
              </div>
            </div>

            <div className="field">
              <div className="field-label-row">
                <label className="field-label" htmlFor="password">
                  Password
                </label>
              </div>
              <div className="field-input-wrap">
                <Lock className="field-icon" size={17} />
                <input
                  className="field-input with-left-icon with-right-icon"
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="••••••••••••"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={isLoading}
                />
                <button
                  type="button"
                  className="field-action-btn"
                  onClick={() => setShowPassword((prev) => !prev)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button className="login-submit" type="submit" disabled={isLoading}>
              {isLoading ? (
                <>
                  <span className="login-spinner" />
                  <span>Signing in…</span>
                </>
              ) : (
                'Sign in to Portal'
              )}
            </button>
          </form>

          <footer className="login-footer">
            <span className="login-dot" aria-hidden="true" />
            <span>Authorized access only · Controlled environment</span>
          </footer>
        </section>
      </div>
    </main>
  )
}