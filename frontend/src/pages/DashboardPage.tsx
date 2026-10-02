import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'

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
import './DashboardPage.css'

interface DashboardData {
  frameworks: BrsrFramework[]
  projects: Project[]
  periods: ReportingPeriod[]
  submissions: Submission[]
}

const MAX_RECENT = 5

/** Map a submission status onto a badge modifier. */
function statusClass(status: string): string {
  switch (status) {
    case 'APPROVED':
    case 'LOCKED':
      return 'dash-status--done'
    case 'CORRECTION_REQUIRED':
      return 'dash-status--action'
    case 'SUBMITTED':
    case 'RESUBMITTED':
      return 'dash-status--progress'
    case 'UNDER_REVIEW':
      return 'dash-status--review'
    default:
      return 'dash-status--draft'
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

export default function DashboardPage() {
  const { user, token, logout } = useAuth()

  const [data, setData] = useState<DashboardData | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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

  return (
    <div className="dash">
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
        <button className="dash-signout" type="button" onClick={logout}>
          Sign out
        </button>
      </header>

      <div className="dash-body">
        <section className="dash-welcome">
          <div className="dash-welcome-main">
            <h2 className="dash-welcome-title">
              Welcome back, {user?.full_name ?? 'there'}
            </h2>
            <p className="dash-welcome-sub">
              Here is your current ESG reporting position.
            </p>
          </div>
          <dl className="dash-identity">
            <div className="dash-identity-item">
              <dt>Email</dt>
              <dd>{user?.email ?? '—'}</dd>
            </div>
            <div className="dash-identity-item">
              <dt>Organisation</dt>
              <dd title={user?.organization_id ?? undefined}>
                {user?.organization_id ?? 'Not assigned'}
              </dd>
            </div>
          </dl>
        </section>

        {error && (
          <div className="dash-alert" role="alert">
            <span>{error}</span>
            <button
              className="dash-retry"
              type="button"
              onClick={() => void load()}
            >
              Retry
            </button>
          </div>
        )}

        <section className="dash-stats" aria-label="Summary">
          <Stat label="Projects" value={data?.projects.length} loading={isLoading} />
          <Stat
            label="Reporting periods"
            value={data?.periods.length}
            loading={isLoading}
          />
          <Stat
            label="Submissions"
            value={data?.submissions.length}
            loading={isLoading}
          />
          <Stat
            label="BRSR frameworks"
            value={data?.frameworks.length}
            loading={isLoading}
          />
        </section>

        <div className="dash-columns">
          <Panel
            title="BRSR Frameworks"
            subtitle="Reporting standards available to your entity"
            loading={isLoading}
            errored={error !== null}
          >
            {data && data.frameworks.length > 0 ? (
              <ul className="dash-list">
                {data.frameworks.map((framework) => (
                  <li className="dash-row" key={framework.id}>
                    <div className="dash-row-head">
                      <span className="dash-row-title">{framework.name}</span>
                      <span className="dash-chip">v{framework.version}</span>
                    </div>
                    {framework.description && (
                      <p className="dash-row-note">{framework.description}</p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <Empty />
            )}
          </Panel>

          <Panel
            title="Projects"
            subtitle="Sites and facilities within your scope"
            loading={isLoading}
            errored={error !== null}
          >
            {data && data.projects.length > 0 ? (
              <ul className="dash-list">
                {data.projects.map((project) => (
                  <li className="dash-row" key={project.id}>
                    <div className="dash-row-head">
                      <span className="dash-row-title">{project.name}</span>
                      {project.code && (
                        <span className="dash-chip dash-chip--plain">
                          {project.code}
                        </span>
                      )}
                    </div>
                    {project.location && (
                      <p className="dash-row-note">{project.location}</p>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <Empty message="No projects in scope." />
            )}
          </Panel>
        </div>

        <Panel
          title="Recent Submissions"
          subtitle="Most recent disclosure submissions"
          loading={isLoading}
          errored={error !== null}
        >
          {recent.length > 0 ? (
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <th scope="col">Status</th>
                    <th scope="col">Project</th>
                    <th scope="col">Reporting period</th>
                    <th scope="col">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {recent.map((submission) => (
                    <tr key={submission.id}>
                      <td>
                        <span
                          className={`dash-status ${statusClass(submission.status)}`}
                        >
                          {submission.status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td>{projectName(submission.project_id)}</td>
                      <td>{periodLabel(submission.reporting_period_id)}</td>
                      <td>{formatDate(submission.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty message="No submissions yet." />
          )}
        </Panel>
      </div>
    </div>
  )
}

function Stat({
  label,
  value,
  loading,
}: {
  label: string
  value: number | undefined
  loading: boolean
}) {
  return (
    <div className="dash-stat">
      <span className="dash-stat-value">
        {loading || value === undefined ? '—' : value}
      </span>
      <span className="dash-stat-label">{label}</span>
    </div>
  )
}

function Panel({
  title,
  subtitle,
  loading,
  errored,
  children,
}: {
  title: string
  subtitle: string
  loading: boolean
  errored: boolean
  children: ReactNode
}) {
  return (
    <section className="dash-panel">
      <header className="dash-panel-head">
        <h3 className="dash-panel-title">{title}</h3>
        <p className="dash-panel-sub">{subtitle}</p>
      </header>
      {loading && <p className="dash-muted">Loading…</p>}
      {!loading && !errored && children}
    </section>
  )
}

function Empty({ message = 'Nothing to show yet.' }: { message?: string }) {
  return <p className="dash-empty">{message}</p>
}
