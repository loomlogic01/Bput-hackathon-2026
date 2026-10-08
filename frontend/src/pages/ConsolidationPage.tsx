import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  Download,
  Calendar,
  BookOpen,
  Building2,
  BarChart3,
  Layers,
  Leaf,
  LogOut,
  AlertTriangle,
  TrendingUp,
} from 'lucide-react'

import type {
  BrsrFramework,
  ConsolidatedDerivedKPI,
  ConsolidationResponse,
  ReportingPeriod,
} from '../api/client'
import {
  API_BASE_URL,
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
  const { user, token, logout } = useAuth()

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
        `${API_BASE_URL}/reporting/consolidation/pdf?reporting_period_id=${periodId}&framework_id=${frameworkId}`,
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

  const userInitial = user?.full_name ? user.full_name[0].toUpperCase() : 'U'

  return (
    <div className="dash">
      {/* Top bar — matches modern DashboardPage navigation */}
      <header className="dash-topbar">
        <div className="dash-brand">
          <div className="dash-brand-mark">
            <Leaf size={18} />
          </div>
          <div className="dash-brand-text">
            <span className="dash-brand-eyebrow">SEBI BRSR CORE</span>
            <p className="dash-brand-name">ESG &amp; Sustainability Portal</p>
          </div>
        </div>

        <nav className="dash-nav-links" aria-label="Main Navigation">
          <button className="dash-nav-link" type="button" onClick={onBack}>
            <Layers size={15} />
            <span>Dashboard</span>
          </button>
          <button className="dash-nav-link dash-nav-link--active" type="button">
            <BarChart3 size={15} />
            <span>Consolidation</span>
          </button>
        </nav>

        <div className="dash-topbar-actions">
          <button className="dash-btn-back" type="button" onClick={onBack}>
            <ArrowLeft size={15} />
            <span>Back to Dashboard</span>
          </button>

          <div className="dash-user-pill">
            <div className="dash-user-avatar">
              {userInitial}
            </div>
            <div className="dash-user-info">
              <span className="dash-user-name">{user?.full_name ?? 'User'}</span>
            </div>
          </div>

          <button className="dash-signout-btn" type="button" onClick={logout}>
            <LogOut size={15} />
            <span className="dash-signout-text">Sign out</span>
          </button>
        </div>
      </header>

      <main className="con-body">
        {/* Page Title & Action Bar */}
        <section className="con-header-bar">
          <div>
            <div className="con-badge-tag">
              <TrendingUp size={13} />
              <span>Multi-Site Aggregation Engine</span>
            </div>
            <h2 className="con-page-title">ESG Consolidation Analytics</h2>
            <p className="con-page-subtitle">
              Aggregate operational metrics across approved site submissions and calculate derived compliance KPIs.
            </p>
          </div>

          {result && (
            <button
              className="con-btn-download"
              type="button"
              disabled={pdfLoading}
              onClick={handleDownloadPdf}
            >
              {pdfLoading ? (
                <>
                  <span className="login-spinner" style={{ width: '14px', height: '14px' }} />
                  <span>Compiling PDF…</span>
                </>
              ) : (
                <>
                  <Download size={16} />
                  <span>Download Official PDF</span>
                </>
              )}
            </button>
          )}
        </section>

        {pdfError && (
          <div className="dash-alert" role="alert">
            <div className="dash-alert-content">
              <AlertTriangle size={18} />
              <span>{pdfError}</span>
            </div>
          </div>
        )}

        {/* ── Selectors Toolbar ── */}
        <section className="con-selectors" aria-label="Consolidation Filters">
          <div className="con-field">
            <label htmlFor="con-period" className="con-label">
              <Calendar size={13} />
              <span>Reporting Period</span>
            </label>
            {selectorsLoading ? (
              <p className="con-select-loading">Loading periods…</p>
            ) : selectorsError ? (
              <p className="con-select-error">{selectorsError}</p>
            ) : periods.length === 0 ? (
              <p className="con-select-empty">No periods available.</p>
            ) : (
              <select
                id="con-period"
                className="con-select"
                value={periodId}
                onChange={(e) => setPeriodId(e.target.value)}
              >
                <option value="">— Select Reporting Period —</option>
                {periods.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.fiscal_year}
                    {p.description ? ` (${p.description})` : ''}
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="con-field">
            <label htmlFor="con-framework" className="con-label">
              <BookOpen size={13} />
              <span>BRSR Framework</span>
            </label>
            {selectorsLoading ? (
              <p className="con-select-loading">Loading frameworks…</p>
            ) : selectorsError ? (
              <p className="con-select-error">{selectorsError}</p>
            ) : frameworks.length === 0 ? (
              <p className="con-select-empty">No frameworks available.</p>
            ) : (
              <select
                id="con-framework"
                className="con-select"
                value={frameworkId}
                onChange={(e) => setFrameworkId(e.target.value)}
              >
                <option value="">— Select BRSR Framework —</option>
                {frameworks.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name} v{f.version}
                  </option>
                ))}
              </select>
            )}
          </div>
        </section>

        {/* ── States: not yet selected ── */}
        {!periodId || !frameworkId ? (
          <div className="con-hint-card">
            <div className="con-hint-icon">
              <BarChart3 size={32} />
            </div>
            <h3 className="con-hint-title">Select Parameters to Consolidate</h3>
            <p className="con-hint-desc">
              Choose both a reporting period and a BRSR framework above to aggregate all approved facility submissions into unified disclosure tables.
            </p>
          </div>
        ) : isLoading ? (
          <div className="con-loading-card">
            <div className="dash-panel-spinner" style={{ width: '2rem', height: '2rem' }} />
            <p>Aggregating and consolidating project disclosures…</p>
          </div>
        ) : error ? (
          <div className="dash-alert" role="alert">
            <div className="dash-alert-content">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
            <button
              className="dash-retry"
              type="button"
              onClick={() => {
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
          <div className="con-results-container">
            {/* ── Summary Stats Cards ── */}
            <section className="dash-stats" aria-label="Aggregation Totals">
              <div className="dash-stat-card dash-stat-card--emerald">
                <div className="dash-stat-top">
                  <span className="dash-stat-label">Contributing Projects</span>
                  <div className="dash-stat-icon-wrap">
                    <Building2 size={20} />
                  </div>
                </div>
                <div className="dash-stat-value">
                  {result.totals.projects_contributing}
                </div>
                <span className="dash-stat-caption">Approved / Locked site filings</span>
              </div>

              <div className="dash-stat-card dash-stat-card--teal">
                <div className="dash-stat-top">
                  <span className="dash-stat-label">Aggregated Metrics</span>
                  <div className="dash-stat-icon-wrap">
                    <BarChart3 size={20} />
                  </div>
                </div>
                <div className="dash-stat-value">
                  {result.totals.metrics_aggregated}
                </div>
                <span className="dash-stat-caption">Combined disclosure data points</span>
              </div>

              <div className="dash-stat-card dash-stat-card--blue">
                <div className="dash-stat-top">
                  <span className="dash-stat-label">Reporting Period</span>
                  <div className="dash-stat-icon-wrap">
                    <Calendar size={20} />
                  </div>
                </div>
                <div className="dash-stat-value" style={{ fontSize: '1.25rem' }}>
                  {selectedPeriod?.fiscal_year ?? '—'}
                </div>
                <span className="dash-stat-caption">{selectedPeriod?.description || 'Active Fiscal Year'}</span>
              </div>

              <div className="dash-stat-card dash-stat-card--slate">
                <div className="dash-stat-top">
                  <span className="dash-stat-label">Framework Model</span>
                  <div className="dash-stat-icon-wrap">
                    <BookOpen size={20} />
                  </div>
                </div>
                <div className="dash-stat-value" style={{ fontSize: '1.25rem' }}>
                  {selectedFramework?.name ?? '—'}
                </div>
                <span className="dash-stat-caption">Version {selectedFramework?.version ?? '1.0'}</span>
              </div>
            </section>

            {/* ── Derived KPI hero card ── */}
            {renewableKpi && (
              <div className="con-kpi-hero" aria-label="Derived Key Performance Indicator">
                <div className="con-kpi-hero-header">
                  <span className="con-kpi-hero-eyebrow">SEBI CORE DERIVED KPI</span>
                  <span className="con-kpi-hero-status">Verified Formula</span>
                </div>
                <h3 className="con-kpi-hero-label">{renewableKpi.label}</h3>

                {renewableKpi.value !== null ? (
                  <div className="con-kpi-hero-stat-row">
                    <span className="con-kpi-hero-value">
                      {renewableKpi.value.toFixed(2)}
                    </span>
                    <span className="con-kpi-hero-unit">{renewableKpi.unit}</span>
                  </div>
                ) : (
                  <p className="con-kpi-hero-null">Value not available in this dataset</p>
                )}

                <div className="con-kpi-hero-meta">
                  <div className="con-kpi-meta-badge">
                    <span className="con-kpi-meta-label">Calculation:</span>
                    <strong className="con-kpi-meta-val">
                      {renewableKpi.calculation_method.replace(/-/g, ' ')}
                    </strong>
                  </div>
                  <div className="con-kpi-meta-badge">
                    <span className="con-kpi-meta-label">Facilities:</span>
                    <strong className="con-kpi-meta-val">
                      {renewableKpi.contributing_project_count} Contributing Sites
                    </strong>
                  </div>
                  <div className="con-kpi-meta-badge">
                    <span className="con-kpi-meta-label">Source Codes:</span>
                    <strong className="con-kpi-meta-val">
                      {renewableKpi.source_question_codes.join(', ')}
                    </strong>
                  </div>
                </div>
              </div>
            )}

            {/* ── Consolidated metrics table ── */}
            <section className="dash-panel" aria-label="Consolidated Metrics Table">
              <header className="dash-panel-head">
                <div className="dash-panel-title-group">
                  <div className="dash-panel-icon">
                    <BarChart3 size={18} />
                  </div>
                  <div>
                    <h3 className="dash-panel-title">Consolidated Metric Disclosures</h3>
                    <p className="dash-panel-sub">
                      Aggregated operational values synthesized across all contributing projects
                    </p>
                  </div>
                </div>
              </header>

              {result.metrics.length === 0 ? (
                <div className="dash-empty">
                  <p className="dash-empty-text">No metrics found for this aggregation.</p>
                </div>
              ) : (
                <div className="dash-table-wrap">
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th scope="col">Code</th>
                        <th scope="col">Metric / Question Description</th>
                        <th scope="col">Aggregated Value</th>
                        <th scope="col">Unit</th>
                        <th scope="col">Sites</th>
                        <th scope="col">Formula</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.metrics.map((m) => (
                        <tr
                          key={m.question_code}
                          className={
                            !m.aggregated_value_is_meaningful
                              ? 'con-warn-row'
                              : 'dash-table-row'
                          }
                        >
                          <td>
                            <span className="dash-badge-code">
                              {m.question_code}
                            </span>
                          </td>
                          <td>
                            <span className="con-metric-text">{m.question}</span>
                          </td>
                          <td>
                            <div className="con-value-cell">
                              <span className="con-value-num">
                                {m.aggregated_value.toFixed(2)}
                              </span>
                              {!m.aggregated_value_is_meaningful && (
                                <span
                                  className="con-warn-badge"
                                  title="Raw sum — not a meaningful consolidated KPI"
                                >
                                  <AlertTriangle size={12} />
                                  <span>Raw Sum</span>
                                </span>
                              )}
                            </div>
                          </td>
                          <td>
                            <span className="con-unit-badge">
                              {m.unit_of_measurement || '—'}
                            </span>
                          </td>
                          <td>
                            <span className="con-count-badge">
                              {m.contributing_project_count}
                            </span>
                          </td>
                          <td>
                            <span className="dash-period-badge">
                              {m.aggregation}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            {/* ── Contributing projects table ── */}
            <section className="dash-panel" aria-label="Contributing Projects Table">
              <header className="dash-panel-head">
                <div className="dash-panel-title-group">
                  <div className="dash-panel-icon">
                    <Building2 size={18} />
                  </div>
                  <div>
                    <h3 className="dash-panel-title">Contributing Facilities</h3>
                    <p className="dash-panel-sub">
                      Approved or locked project filings in this reporting period
                    </p>
                  </div>
                </div>
              </header>

              {result.projects.length === 0 ? (
                <div className="dash-empty">
                  <p className="dash-empty-text">No projects have approved submissions for this period.</p>
                </div>
              ) : (
                <div className="dash-table-wrap">
                  <table className="dash-table">
                    <thead>
                      <tr>
                        <th scope="col">Project Code</th>
                        <th scope="col">Facility Name</th>
                        <th scope="col">Filing Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.projects.map((p: any) => (
                        <tr key={p.project_id ?? p.id ?? p.project_code} className="dash-table-row">
                          <td>
                            <span className="dash-badge-code">
                              {p.project_code ?? '—'}
                            </span>
                          </td>
                          <td>
                            <strong className="dash-project-name">
                              {p.project_name ?? p.name ?? '—'}
                            </strong>
                          </td>
                          <td>
                            <span
                              className={`dash-status-pill ${
                                p.submission_status === 'APPROVED' ||
                                p.submission_status === 'LOCKED'
                                  ? 'dash-status--done'
                                  : 'dash-status--draft'
                              }`}
                            >
                              <span className="dash-status-dot" />
                              <span>{p.submission_status?.replace(/_/g, ' ') ?? '—'}</span>
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          </div>
        )}
      </main>
    </div>
  )
}


