import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Building2,
  Calendar,
  ClipboardCheck,
  BookOpen,
  Plus,
  BarChart3,
  History,
  LogOut,
  Leaf,
  FileEdit,
  ShieldAlert,
  MapPin,
  RefreshCw,
  Clock,
  Layers,
} from 'lucide-react'

import type {
  BrsrFramework,
  Project,
  ReportingPeriod,
  Submission,
} from '../api/client'
import {
  ApiError,
  listFrameworks,
  listProjects,
  listReportingPeriods,
  listSubmissions,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import ApproverSubmissionPage from './ApproverSubmissionPage'
import NewSubmissionPage from './NewSubmissionPage'
import ReviewerSubmissionPage from './ReviewerSubmissionPage'
import SubmissionFormPage from './SubmissionFormPage'
import './DashboardPage.css'

interface DashboardData {
  frameworks: BrsrFramework[]
  projects: Project[]
  periods: ReportingPeriod[]
  submissions: Submission[]
}

const MAX_RECENT = 8

/** Map a submission status onto a badge modifier and dot. */
function statusConfig(status: string): { className: string; label: string } {
  switch (status) {
    case 'APPROVED':
      return { className: 'dash-status--done', label: 'Approved' }
    case 'LOCKED':
      return { className: 'dash-status--locked', label: 'Locked' }
    case 'CORRECTION_REQUIRED':
      return { className: 'dash-status--action', label: 'Correction Required' }
    case 'SUBMITTED':
      return { className: 'dash-status--progress', label: 'Submitted' }
    case 'RESUBMITTED':
      return { className: 'dash-status--progress', label: 'Resubmitted' }
    case 'UNDER_REVIEW':
      return { className: 'dash-status--review', label: 'Under Review' }
    default:
      return { className: 'dash-status--draft', label: 'Draft' }
  }
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default function DashboardPage({
  onNavigate,
}: {
  onNavigate?: (page: 'consolidation' | 'audit') => void
}) {
  const { user, token, logout } = useAuth()

  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showNewSubmission, setShowNewSubmission] = useState(false)
  const [openSubmissionId, setOpenSubmissionId] = useState<string | null>(null)
  const [reviewSubmissionId, setReviewSubmissionId] = useState<string | null>(null)
  const [approveSubmissionId, setApproveSubmissionId] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!token) return
    setIsLoading(true)
    setError(null)
    try {
      // The four reads are independent, so issue them together.
      const [frameworks, projects, periods, submissions] = await Promise.all([
        listFrameworks(token),
        listProjects(token),
        listReportingPeriods(token),
        listSubmissions(token),
      ])
      setData({ frameworks, projects, periods, submissions })
    } catch (err) {
      setData(null)
      if (err instanceof ApiError) {
        setError(
          err.status === 401
            ? 'Your session has expired. Please sign in again.'
            : err.message,
        )
      } else {
        setError('Unable to load dashboard data.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [token])

  useEffect(() => {
    void load()
  }, [load])

  const recent: Submission[] = data
    ? [...data.submissions]
        .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''))
        .slice(0, MAX_RECENT)
    : []

  const projectName = (id: string): string =>
    data?.projects.find((p) => p.id === id)?.name ?? '—'

  const periodLabel = (id: string): string =>
    data?.periods.find((p) => p.id === id)?.fiscal_year ?? '—'

  const userInitial = user?.full_name ? user.full_name[0].toUpperCase() : 'U'

  return (
    <div className="dash">
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

        {/* Global Navigation Tabs */}
        <nav className="dash-nav-links" aria-label="Main Navigation">
          <button className="dash-nav-link dash-nav-link--active" type="button">
            <Layers size={15} />
            <span>Dashboard</span>
          </button>
          {onNavigate && (
            <>
              <button
                className="dash-nav-link"
                type="button"
                onClick={() => onNavigate('consolidation')}
              >
                <BarChart3 size={15} />
                <span>Consolidation</span>
              </button>
              <button
                className="dash-nav-link"
                type="button"
                onClick={() => onNavigate('audit')}
              >
                <History size={15} />
                <span>Audit Log</span>
              </button>
            </>
          )}
        </nav>

        <div className="dash-topbar-actions">
          <button
            className="dash-primary-btn"
            type="button"
            onClick={() => setShowNewSubmission(true)}
          >
            <Plus size={16} />
            <span>New Submission</span>
          </button>

          <div className="dash-user-pill">
            <div className="dash-user-avatar" title={user?.email ?? undefined}>
              {userInitial}
            </div>
            <div className="dash-user-info">
              <span className="dash-user-name">{user?.full_name ?? 'User'}</span>
            </div>
          </div>

          <button
            className="dash-signout-btn"
            type="button"
            onClick={logout}
            title="Sign out of your session"
          >
            <LogOut size={15} />
            <span className="dash-signout-text">Sign out</span>
          </button>
        </div>
      </header>

      {openSubmissionId !== null ? (
        <SubmissionFormPage
          submissionId={openSubmissionId}
          onClose={() => setOpenSubmissionId(null)}
        />
      ) : reviewSubmissionId !== null ? (
        <ReviewerSubmissionPage
          submissionId={reviewSubmissionId}
          onClose={() => setReviewSubmissionId(null)}
        />
      ) : approveSubmissionId !== null ? (
        <ApproverSubmissionPage
          submissionId={approveSubmissionId}
          onClose={() => setApproveSubmissionId(null)}
        />
      ) : showNewSubmission ? (
        <NewSubmissionPage
          onCreated={() => {
            void load()
          }}
          onCancel={() => setShowNewSubmission(false)}
        />
      ) : (
        <main className="dash-body">
          {/* Welcome Executive Banner */}
          <section className="dash-welcome">
            <div className="dash-welcome-main">
              <div className="dash-welcome-tag">
                <span className="dash-live-dot" />
                <span>Regulatory Cycle 2026 Active</span>
              </div>
              <h2 className="dash-welcome-title">
                Welcome back, {user?.full_name ?? 'Reporting Officer'}
              </h2>
              <p className="dash-welcome-sub">
                Manage ESG indicators, monitor multi-facility disclosures, and prepare SEBI BRSR Core submissions.
              </p>
            </div>

            <div className="dash-identity-cards">
              <div className="dash-identity-card">
                <span className="dash-identity-label">Account</span>
                <span className="dash-identity-value">{user?.email ?? '—'}</span>
              </div>
              <div className="dash-identity-card">
                <span className="dash-identity-label">Organisation ID</span>
                <span className="dash-identity-value font-mono">
                  {user?.organization_id ? user.organization_id.slice(0, 13) + '…' : 'General Node'}
                </span>
              </div>
            </div>
          </section>

          {error && (
            <div className="dash-alert" role="alert">
              <div className="dash-alert-content">
                <ShieldAlert size={18} />
                <span>{error}</span>
              </div>
              <button
                className="dash-retry"
                type="button"
                onClick={() => void load()}
              >
                <RefreshCw size={14} />
                <span>Retry</span>
              </button>
            </div>
          )}

          {/* Metric Stats Cards */}
          <section className="dash-stats" aria-label="Key Performance Statistics">
            <Stat
              label="Projects in Scope"
              value={data?.projects.length}
              caption="Reporting sites & facilities"
              icon={<Building2 size={20} />}
              loading={isLoading}
              colorVariant="emerald"
            />
            <Stat
              label="Reporting Periods"
              value={data?.periods.length}
              caption="Fiscal compliance timelines"
              icon={<Calendar size={20} />}
              loading={isLoading}
              colorVariant="blue"
            />
            <Stat
              label="Total Submissions"
              value={data?.submissions.length}
              caption="Filings in progress & approved"
              icon={<ClipboardCheck size={20} />}
              loading={isLoading}
              colorVariant="teal"
            />
            <Stat
              label="BRSR Frameworks"
              value={data?.frameworks.length}
              caption="Standards & indicator sets"
              icon={<BookOpen size={20} />}
              loading={isLoading}
              colorVariant="slate"
            />
          </section>

          {/* Dual Columns: Frameworks & Projects */}
          <div className="dash-columns">
            <Panel
              title="BRSR Frameworks"
              subtitle="SEBI National Standards & Disclosure Sets"
              icon={<BookOpen size={17} />}
              loading={isLoading}
              errored={error !== null}
            >
              {data && data.frameworks.length > 0 ? (
                <ul className="dash-list">
                  {data.frameworks.map((framework) => (
                    <li className="dash-card-item" key={framework.id}>
                      <div className="dash-card-header">
                        <div className="dash-card-title-group">
                          <span className="dash-card-title">{framework.name}</span>
                          <span className="dash-badge-version">v{framework.version}</span>
                        </div>
                        <span className="dash-tag-standard">SEBI Standard</span>
                      </div>
                      {framework.description && (
                        <p className="dash-card-note">{framework.description}</p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty message="No BRSR frameworks configured yet." />
              )}
            </Panel>

            <Panel
              title="Registered Facilities & Projects"
              subtitle="Sites currently contributing operational ESG metrics"
              icon={<Building2 size={17} />}
              loading={isLoading}
              errored={error !== null}
            >
              {data && data.projects.length > 0 ? (
                <ul className="dash-list">
                  {data.projects.map((project) => (
                    <li className="dash-card-item" key={project.id}>
                      <div className="dash-card-header">
                        <div className="dash-card-title-group">
                          <span className="dash-card-title">{project.name}</span>
                          {project.code && (
                            <span className="dash-badge-code">{project.code}</span>
                          )}
                        </div>
                      </div>
                      {project.location ? (
                        <p className="dash-card-location">
                          <MapPin size={13} />
                          <span>{project.location}</span>
                        </p>
                      ) : (
                        <p className="dash-card-location muted">Location unspecified</p>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <Empty message="No active projects within scope." />
              )}
            </Panel>
          </div>

          {/* Recent Submissions Table Panel */}
          <Panel
            title="Recent Disclosure Submissions"
            subtitle="Filings across all projects and workflow phases"
            icon={<ClipboardCheck size={18} />}
            loading={isLoading}
            errored={error !== null}
            action={
              <button
                className="dash-link-action"
                type="button"
                onClick={() => setShowNewSubmission(true)}
              >
                <span>+ Create Filing</span>
              </button>
            }
          >
            {recent.length > 0 ? (
              <div className="dash-table-wrap">
                <table className="dash-table">
                  <thead>
                    <tr>
                      <th scope="col">Status</th>
                      <th scope="col">Project / Site</th>
                      <th scope="col">Reporting Period</th>
                      <th scope="col">Filing Date</th>
                      <th scope="col" className="text-right">Workflow Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recent.map((submission) => {
                      const cfg = statusConfig(submission.status)
                      return (
                        <tr key={submission.id} className="dash-table-row">
                          <td>
                            <span className={`dash-status-pill ${cfg.className}`}>
                              <span className="dash-status-dot" />
                              <span>{cfg.label}</span>
                            </span>
                          </td>
                          <td>
                            <div className="dash-cell-project">
                              <span className="dash-project-name">
                                {projectName(submission.project_id)}
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className="dash-period-badge">
                              {periodLabel(submission.reporting_period_id)}
                            </span>
                          </td>
                          <td>
                            <span className="dash-date-text">
                              <Clock size={13} />
                              {formatDate(submission.created_at)}
                            </span>
                          </td>
                          <td>
                            <div className="dash-rowactions">
                              <button
                                className="dash-btn-action dash-btn-open"
                                type="button"
                                title="Open response entry form"
                                onClick={() => {
                                  setShowNewSubmission(false)
                                  setReviewSubmissionId(null)
                                  setApproveSubmissionId(null)
                                  setOpenSubmissionId(submission.id)
                                }}
                              >
                                <FileEdit size={13} />
                                <span>Open form</span>
                              </button>
                              <button
                                className="dash-btn-action dash-btn-review"
                                type="button"
                                title="Review responses & audit logs"
                                onClick={() => {
                                  setShowNewSubmission(false)
                                  setOpenSubmissionId(null)
                                  setApproveSubmissionId(null)
                                  setReviewSubmissionId(submission.id)
                                }}
                              >
                                <span>Review</span>
                              </button>
                              <button
                                className="dash-btn-action dash-btn-approve"
                                type="button"
                                title="Approver sign-off"
                                onClick={() => {
                                  setShowNewSubmission(false)
                                  setOpenSubmissionId(null)
                                  setReviewSubmissionId(null)
                                  setApproveSubmissionId(submission.id)
                                }}
                              >
                                <span>Approve</span>
                              </button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty message="No disclosure submissions filed yet. Click 'New Submission' above to get started." />
            )}
          </Panel>
        </main>
      )}
    </div>
  )
}

function Stat({
  label,
  value,
  caption,
  icon,
  loading,
  colorVariant,
}: {
  label: string
  value: number | undefined
  caption?: string
  icon: ReactNode
  loading: boolean
  colorVariant: 'emerald' | 'blue' | 'teal' | 'slate'
}) {
  return (
    <div className={`dash-stat-card dash-stat-card--${colorVariant}`}>
      <div className="dash-stat-top">
        <span className="dash-stat-label">{label}</span>
        <div className="dash-stat-icon-wrap">{icon}</div>
      </div>
      <div className="dash-stat-value">
        {loading || value === undefined ? (
          <span className="dash-stat-skeleton" />
        ) : (
          value
        )}
      </div>
      {caption && <span className="dash-stat-caption">{caption}</span>}
    </div>
  )
}

function Panel({
  title,
  subtitle,
  icon,
  loading,
  errored,
  action,
  children,
}: {
  title: string
  subtitle: string
  icon?: ReactNode
  loading: boolean
  errored: boolean
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="dash-panel">
      <header className="dash-panel-head">
        <div className="dash-panel-title-group">
          {icon && <div className="dash-panel-icon">{icon}</div>}
          <div>
            <h3 className="dash-panel-title">{title}</h3>
            <p className="dash-panel-sub">{subtitle}</p>
          </div>
        </div>
        {action && <div className="dash-panel-action">{action}</div>}
      </header>
      {loading && (
        <div className="dash-panel-loading">
          <div className="dash-panel-spinner" />
          <span>Loading data…</span>
        </div>
      )}
      {!loading && !errored && children}
    </section>
  )
}

function Empty({ message = 'Nothing to show yet.' }: { message?: string }) {
  return (
    <div className="dash-empty">
      <div className="dash-empty-icon">
        <BookOpen size={28} />
      </div>
      <p className="dash-empty-text">{message}</p>
    </div>
  )
}

