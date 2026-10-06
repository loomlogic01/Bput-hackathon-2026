import { useEffect, useState } from 'react'
import type { AuditLog } from '../api/client'
import { ApiError, listAuditLogs } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './DashboardPage.css'
import './ConsolidationPage.css'

interface Props {
  onBack: () => void
}

export default function AuditLogPage({ onBack }: Props) {
  const { token, logout } = useAuth()

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
          <h2 className="con-page-title" style={{ margin: 0 }}>System Audit Log</h2>
          <button className="dash-secondary" type="button" onClick={fetchLogs}>
            🔄 Refresh
          </button>
        </div>

        {/* Filters */}
        <div className="con-selectors" style={{ marginBottom: '1.5rem' }}>
          <div className="con-field">
            <label htmlFor="audit-action-select" className="con-label">
              Action Filter
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
              Entity Type Filter
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
        </div>

        {isLoading ? (
          <p className="dash-muted">Loading audit history…</p>
        ) : error ? (
          <div className="dash-alert" role="alert">
            <span>{error}</span>
            <button className="dash-retry" type="button" onClick={fetchLogs}>
              Retry
            </button>
          </div>
        ) : logs.length === 0 ? (
          <p className="dash-empty">No audit log records found.</p>
        ) : (
          <section className="dash-panel">
            <header className="dash-panel-head">
              <h3 className="dash-panel-title">Activity History</h3>
              <p className="dash-panel-sub">
                Immutable record of platform events ({logs.length} entries shown)
              </p>
            </header>
            <div className="dash-table-wrap">
              <table className="dash-table">
                <thead>
                  <tr>
                    <th scope="col">Timestamp</th>
                    <th scope="col">User ID</th>
                    <th scope="col">Action</th>
                    <th scope="col">Entity</th>
                    <th scope="col">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id}>
                      <td>
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td>
                        <span className="dash-chip dash-chip--plain">
                          {log.user_id ? log.user_id.slice(0, 8) + '…' : 'System'}
                        </span>
                      </td>
                      <td>
                        <span className="dash-chip dash-chip--primary">
                          {log.action}
                        </span>
                      </td>
                      <td>
                        {log.entity_type} {log.entity_id ? `(${log.entity_id.slice(0, 8)}…)` : ''}
                      </td>
                      <td>{log.description || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}

