import { useEffect, useState } from 'react'

import type {
  BrsrFramework,
  ConsolidatedDerivedKPI,
  ConsolidationResponse,
  ReportingPeriod,
} from '../api/client'
import {
  ApiError,
  getConsolidation,
  listFrameworks,
  listReportingPeriods,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './DashboardPage.css'
import './ConsolidationPage.css'

interface Props {
  onBack: () => void
}

export default function ConsolidationPage({ onBack }: Props) {
  const { token, logout } = useAuth()

  // ── selector data ──
  const [periods, setPeriods] = useState<ReportingPeriod[]>([])
  const [frameworks, setFrameworks] = useState<BrsrFramework[]>([])
  const [selectorsLoading, setSelectorsLoading] = useState(true)
  const [selectorsError, setSelectorsError] = useState<string | null>(null)

  // ── selections ──
  const [periodId, setPeriodId] = useState('')
  const [frameworkId, setFrameworkId] = useState('')

  // ── consolidation result ──
  const [result, setResult] = useState<ConsolidationResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // ── PDF download ──
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState<string | null>(null)

  // Load selectors once on mount
  useEffect(() => {
    if (!token) return
    let cancelled = false
    setSelectorsLoading(true)
    Promise.all([listReportingPeriods(token), listFrameworks(token)])
      .then(([p, f]) => {
        if (cancelled) return
        setPeriods(p)
        setFrameworks(f)
      })
      .catch((err) => {
        if (cancelled) return
        setSelectorsError(
          err instanceof ApiError ? err.message : 'Failed to load selector data.',
        )
      })
      .finally(() => {
        if (!cancelled) setSelectorsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [token])

  // Fetch consolidation whenever both IDs are set
  useEffect(() => {
    if (!periodId || !frameworkId || !token) {
      setResult(null)
      return
    }
    let cancelled = false
    setIsLoading(true)
    setError(null)
    setResult(null)
    getConsolidation(periodId, frameworkId, token)
      .then((r) => {
        if (!cancelled) setResult(r)
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof ApiError) {
          setError(
            err.status === 401
              ? 'Your session has expired. Please sign in again.'
              : err.message,
          )
        } else {
          setError('Failed to load consolidation data.')
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [periodId, frameworkId, token])

  const handleDownloadPdf = async () => {
    if (!periodId || !frameworkId || !token) return
    setPdfLoading(true)
    setPdfError(null)
    try {
      const res = await fetch(
        `/api/v1/reporting/consolidation/pdf?reporting_period_id=${periodId}&framework_id=${frameworkId}`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      )
      if (!res.ok) {
        throw new Error(`Failed to download PDF (status ${res.status})`)
      }
      const blob = await res.blob()
      const downloadUrl = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `consolidation_${selectedPeriod?.fiscal_year.replace('/', '-') || periodId}.pdf`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(downloadUrl)
    } catch (err) {
      setPdfError(err instanceof Error ? err.message : 'Error downloading PDF')
    } finally {
      setPdfLoading(false)
    }
  }

  const selectedPeriod = periods.find((p) => p.id === periodId)
  const selectedFramework = frameworks.find((f) => f.id === frameworkId)

  // The first (and likely only) derived KPI
  const renewableKpi: ConsolidatedDerivedKPI | null =
    result?.derived_kpis?.[0] ?? null

  return (
    <div className="dash">
      {/* Top bar — mirrors DashboardPage */}
      <header className="dash-topbar">
        <div className="dash-brand">
          <span className="dash-brand-mark">SEBI</span>
          <div className="dash-brand-text">
            <p className="dash-brand-eyebrow">
              Business Responsibility &amp; Sustainability
            </p>
            <p className="dash-brand-name">ESG Reporting Portal</p>
          </div>
        </div>
        <div className="dash-topbar-actions">
          <button className="dash-primary" type="button" onClick={onBack}>
            ← Dashboard
          </button>
          <button className="dash-signout" type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <div className="con-body">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2 className="con-page-title" style={{ margin: 0 }}>ESG Consolidation</h2>
          {result && (
            <button
              className="dash-primary"
              type="button"
              disabled={pdfLoading}
              onClick={handleDownloadPdf}
            >
              {pdfLoading ? 'Generating PDF…' : '📄 Download PDF'}
            </button>
          )}
        </div>
        {pdfError && (
          <div className="dash-alert" role="alert" style={{ marginBottom: '1rem' }}>
            <span>{pdfError}</span>
          </div>
        )}

        {/* ── Selectors ── */}
        <div className="con-selectors">
          <div className="con-field">
            <label htmlFor="con-period" className="con-label">
              Reporting Period
            </label>
            {selectorsLoading ? (
              <p className="dash-muted">Loading…</p>
            ) : selectorsError ? (
              <p className="dash-muted">{selectorsError}</p>
            ) : periods.length === 0 ? (
              <p className="dash-muted">No reporting periods available.</p>
            ) : (
              <select
                id="con-period"
                className="con-select"
                value={periodId}
                onChange={(e) => setPeriodId(e.target.value)}
              >
                <option value="">— Select a period —</option>
                {periods.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.fiscal_year}
                    {p.description ? ` — ${p.description}` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="con-field">
            <label htmlFor="con-framework" className="con-label">
              BRSR Framework
            </label>
            {selectorsLoading ? (
              <p className="dash-muted">Loading…</p>
            ) : selectorsError ? (
              <p className="dash-muted">{selectorsError}</p>
            ) : frameworks.length === 0 ? (
              <p className="dash-muted">No frameworks available.</p>
            ) : (
              <select
                id="con-framework"
                className="con-select"
                value={frameworkId}
                onChange={(e) => setFrameworkId(e.target.value)}
              >
                <option value="">— Select a framework —</option>
                {frameworks.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} v{f.version}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* ── States: not yet selected ── */}
        {!periodId || !frameworkId ? (
          <p className="con-hint">
            Select a reporting period and a BRSR framework above to view the
            consolidated ESG data.
          </p>
        ) : isLoading ? (
          <p className="dash-muted">Loading consolidation data…</p>
        ) : error ? (
          <div className="dash-alert" role="alert">
            <span>{error}</span>
            <button
              className="dash-retry"
              type="button"
              onClick={() => {
                // Re-trigger by clearing + resetting — simplest without a manual trigger state
                const p = periodId
                const f = frameworkId
                setPeriodId('')
                setFrameworkId('')
                setTimeout(() => {
                  setPeriodId(p)
                  setFrameworkId(f)
                }, 0)
              }}
            >
              Retry
            </button>
          </div>
        ) : result === null ? null : (
          <>
            {/* ── Summary cards ── */}
            <section className="dash-stats" aria-label="Summary">
              <div className="dash-stat">
                <span className="dash-stat-value">
                  {result.totals.projects_contributing}
                </span>
                <span className="dash-stat-label">Projects Contributing</span>
              </div>
              <div className="dash-stat">
                <span className="dash-stat-value">
                  {result.totals.metrics_aggregated}
                </span>
                <span className="dash-stat-label">Metrics Aggregated</span>
              </div>
              <div className="dash-stat">
                <span className="dash-stat-value" style={{ fontSize: '1rem' }}>
                  {selectedPeriod?.fiscal_year ?? '—'}
                </span>
                <span className="dash-stat-label">Reporting Period</span>
              </div>
              <div className="dash-stat">
                <span className="dash-stat-value" style={{ fontSize: '1rem' }}>
                  {selectedFramework?.name ?? '—'}
                </span>
                <span className="dash-stat-label">Framework</span>
              </div>
            </section>

            {/* ── Derived KPI hero ── */}
            {renewableKpi && (
              <div className="con-kpi-hero" aria-label="Derived KPI">
                <p className="con-kpi-hero-eyebrow">Derived KPI</p>
                <p className="con-kpi-hero-label">{renewableKpi.label}</p>
                {renewableKpi.value !== null ? (
                  <p>
                    <span className="con-kpi-hero-value">
                      {renewableKpi.value.toFixed(2)}
                    </span>
                    <span className="con-kpi-hero-unit">{renewableKpi.unit}</span>
                  </p>
                ) : (
                  <p className="con-kpi-hero-null">Value not available</p>
                )}
                <div className="con-kpi-hero-meta">
                  <span>
                    Method:{' '}
                    <strong>
                      {renewableKpi.calculation_method.replace(/-/g, ' ')}
                    </strong>
                  </span>
                  <span>
                    Contributing projects:{' '}
                    <strong>{renewableKpi.contributing_project_count}</strong>
                  </span>
                  <span>
                    Sources:{' '}
                    <strong>{renewableKpi.source_question_codes.join(', ')}</strong>
                  </span>
                </div>
              </div>
            )}

            {/* ── Consolidated metrics table ── */}
            <section className="dash-panel" aria-label="Consolidated Metrics">
              <header className="dash-panel-head">
                <h3 className="dash-panel-title">Consolidated Metrics</h3>
                <p className="dash-panel-sub">
                  Aggregated values across all contributing projects
                </p>
              </header>
              {result.metrics.length === 0 ? (
                <p className="dash-empty">No metrics available.</p>
              ) : (
                <div className="dash-table-wrap">
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th scope="col">Question Code</th>
                        <th scope="col">Question</th>
                        <th scope="col">Aggregated Value</th>
                        <th scope="col">Unit</th>
                        <th scope="col">Contributing Projects</th>
                        <th scope="col">Aggregation</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.metrics.map((m) => (
                        <tr
                          key={m.question_code}
                          className={
                            !m.aggregated_value_is_meaningful
                              ? 'con-warn-row'
                              : ''
                          }
                        >
                          <td>
                            <span className="dash-chip dash-chip--plain">
                              {m.question_code}
                            </span>
                          </td>
                          <td>{m.question}</td>
                          <td>
                            {m.aggregated_value.toFixed(2)}
                            {!m.aggregated_value_is_meaningful && (
                              <>
                                {' '}
                                <span
                                  className="con-warn-badge"
                                  title="Raw sum — not a meaningful consolidated KPI"
                                >
                                  ⚠ Not a KPI
                                </span>
                              </>
                            )}
                          </td>
                          <td>{m.unit_of_measurement || '—'}</td>
                          <td>{m.contributing_project_count}</td>
                          <td>{m.aggregation}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* ── Contributing projects table ── */}
            <section className="dash-panel" aria-label="Contributing Projects">
              <header className="dash-panel-head">
                <h3 className="dash-panel-title">Contributing Projects</h3>
                <p className="dash-panel-sub">
                  Projects with approved or locked submissions in this period
                </p>
              </header>
              {result.projects.length === 0 ? (
                <p className="dash-empty">No contributing projects.</p>
              ) : (
                <div className="dash-table-wrap">
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th scope="col">Project Code</th>
                        <th scope="col">Project Name</th>
                        <th scope="col">Submission Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.projects.map((p: any) => (
                        <tr key={p.project_id ?? p.id ?? p.project_code}>
                          <td>
                            <span className="dash-chip dash-chip--plain">
                              {p.project_code ?? '—'}
                            </span>
                          </td>
                          <td>{p.project_name ?? p.name ?? '—'}</td>
                          <td>
                            <span
                              className={`dash-status ${
                                p.submission_status === 'APPROVED' ||
                                p.submission_status === 'LOCKED'
                                  ? 'dash-status--done'
                                  : 'dash-status--draft'
                              }`}
                            >
                              {p.submission_status?.replace(/_/g, ' ') ?? '—'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </>
        )}
      </div>
    </div>
  )
}

