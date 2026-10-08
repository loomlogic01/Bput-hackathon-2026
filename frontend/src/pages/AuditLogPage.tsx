import { useEffect, useState } from 'react'
import {
  ArrowLeft,
  RefreshCw,
  History,
  ShieldCheck,
  Filter,
  Clock,
  Layers,
  Leaf,
  LogOut,
  AlertTriangle,
  Database,
  KeyRound,
  FileCheck2,
} from 'lucide-react'

import type { AuditLog } from '../api/client'
import { ApiError, listAuditLogs } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './DashboardPage.css'
import './ConsolidationPage.css'

interface Props {
  onBack: () => void
}

function actionBadge(action: string) {
  switch (action) {
    case 'USER_LOGIN':
      return { className: 'dash-status--progress', icon: <KeyRound size={12} /> }
    case 'VALUE_UPDATED':
      return { className: 'dash-status--done', icon: <FileCheck2 size={12} /> }
    case 'EVIDENCE_UPLOADED':
      return { className: 'dash-status--review', icon: <Database size={12} /> }
    default:
      return { className: 'dash-status--draft', icon: <ShieldCheck size={12} /> }
  }
}

export default function AuditLogPage({ onBack }: Props) {
  const { user, token, logout } = useAuth()

  const [logs, setLogs] = useState<AuditLog[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filter selections
  const [actionFilter, setActionFilter] = useState('')
  const [entityTypeFilter, setEntityTypeFilter] = useState('')

  const fetchLogs = () => {
    if (!token) return
    setIsLoading(true)
    setError(null)
    listAuditLogs(token, {
      limit: 100,
      action: actionFilter || undefined,
      entity_type: entityTypeFilter || undefined,
    })
      .then((data) => {
        setLogs(data)
      })
      .catch((err) => {
        setError(
          err instanceof ApiError
            ? err.message
            : 'Failed to load audit log history.',
        )
      })
      .finally(() => {
        setIsLoading(false)
      })
  }

  useEffect(() => {
    fetchLogs()
  }, [token, actionFilter, entityTypeFilter])

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

        <nav className="dash-nav-links" aria-label="Main Navigation">
          <button className="dash-nav-link" type="button" onClick={onBack}>
            <Layers size={15} />
            <span>Dashboard</span>
          </button>
          <button className="dash-nav-link dash-nav-link--active" type="button">
            <History size={15} />
            <span>Audit Log</span>
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
        <section className="con-header-bar">
          <div>
            <div className="con-badge-tag">
              <ShieldCheck size={13} />
              <span>Immutable Ledger · Regulatory Audit Trail</span>
            </div>
            <h2 className="con-page-title">Platform Audit Trail</h2>
            <p className="con-page-subtitle">
              Cryptographically timestamped record of user authentications, disclosure changes, and file uploads.
            </p>
          </div>

          <button
            className="dash-primary-btn"
            type="button"
            onClick={fetchLogs}
            disabled={isLoading}
          >
            <RefreshCw size={14} className={isLoading ? 'login-spinner' : ''} />
            <span>Refresh Logs</span>
          </button>
        </section>

        {/* Filters Toolbar */}
        <section className="con-selectors" aria-label="Audit Log Filters">
          <div className="con-field">
            <label htmlFor="audit-action-select" className="con-label">
              <Filter size={13} />
              <span>Action Event Filter</span>
            </label>
            <select
              id="audit-action-select"
              className="con-select"
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
            >
              <option value="">All Actions</option>
              <option value="USER_LOGIN">USER_LOGIN</option>
              <option value="VALUE_UPDATED">VALUE_UPDATED</option>
              <option value="EVIDENCE_UPLOADED">EVIDENCE_UPLOADED</option>
            </select>
          </div>

          <div className="con-field">
            <label htmlFor="audit-entity-select" className="con-label">
              <Database size={13} />
              <span>Target Entity Type</span>
            </label>
            <select
              id="audit-entity-select"
              className="con-select"
              value={entityTypeFilter}
              onChange={(e) => setEntityTypeFilter(e.target.value)}
            >
              <option value="">All Entities</option>
              <option value="User">User</option>
              <option value="SubmissionValue">SubmissionValue</option>
              <option value="Evidence">Evidence</option>
            </select>
          </div>
        </section>

        {isLoading ? (
          <div className="con-loading-card">
            <div className="dash-panel-spinner" style={{ width: '2rem', height: '2rem' }} />
            <p>Fetching immutable audit history from database…</p>
          </div>
        ) : error ? (
          <div className="dash-alert" role="alert">
            <div className="dash-alert-content">
              <AlertTriangle size={18} />
              <span>{error}</span>
            </div>
            <button className="dash-retry" type="button" onClick={fetchLogs}>
              Retry
            </button>
          </div>
        ) : logs.length === 0 ? (
          <div className="con-hint-card">
            <div className="con-hint-icon">
              <ShieldCheck size={32} />
            </div>
            <h3 className="con-hint-title">No Audit Records Found</h3>
            <p className="con-hint-desc">
              No events matched the currently selected action and entity filters. Try clearing the filter options.
            </p>
          </div>
        ) : (
          <section className="dash-panel" aria-label="System Activity History">
            <header className="dash-panel-head">
              <div className="dash-panel-title-group">
                <div className="dash-panel-icon">
                  <History size={18} />
                </div>
                <div>
                  <h3 className="dash-panel-title">System Event Ledger</h3>
                  <p className="dash-panel-sub">
                    Displaying latest {logs.length} events logged in this reporting space
                  </p>
                </div>
              </div>
            </header>

            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <th scope="col">Timestamp</th>
                    <th scope="col">Actor / User ID</th>
                    <th scope="col">Action Type</th>
                    <th scope="col">Entity Reference</th>
                    <th scope="col">Event Description</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => {
                    const cfg = actionBadge(log.action)
                    return (
                      <tr key={log.id} className="dash-table-row">
                        <td>
                          <span className="dash-date-text">
                            <Clock size={13} />
                            {new Date(log.created_at).toLocaleString()}
                          </span>
                        </td>
                        <td>
                          <span className="dash-badge-code">
                            {log.user_id ? log.user_id.slice(0, 8) + '…' : 'System'}
                          </span>
                        </td>
                        <td>
                          <span className={`dash-status-pill ${cfg.className}`}>
                            {cfg.icon}
                            <span>{log.action}</span>
                          </span>
                        </td>
                        <td>
                          <span className="dash-period-badge">
                            {log.entity_type} {log.entity_id ? `(${log.entity_id.slice(0, 8)}…)` : ''}
                          </span>
                        </td>
                        <td>
                          <span className="con-metric-text">{log.description || '—'}</span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}


