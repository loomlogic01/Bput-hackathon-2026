import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Building2,
  Calendar,
  BookOpen,
  FileText,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  X,
  Sparkles,
  ClipboardCheck,
} from 'lucide-react'

import type {
  BrsrFramework,
  Project,
  ReportingPeriod,
  Submission,
} from '../api/client'
import {
  ApiError,
  createSubmission,
  listFrameworks,
  listProjects,
  listReportingPeriods,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './NewSubmissionPage.css'

interface Props {
  /** Called with the created submission so the caller can refresh its list. */
  onCreated: (submission: Submission) => void
  onCancel: () => void
}

interface Options {
  projects: Project[]
  periods: ReportingPeriod[]
  frameworks: BrsrFramework[]
}

const EMPTY: Options = { projects: [], periods: [], frameworks: [] }

/** Turn FastAPI's 422 detail array into one readable line. */
function describeValidation(details: unknown[]): string | null {
  const messages = details
    .map((item) => {
      if (item && typeof item === 'object' && 'msg' in item) {
        const loc = (item as { loc?: unknown[] }).loc
        const field = Array.isArray(loc) ? String(loc[loc.length - 1]) : ''
        const msg = String((item as { msg?: unknown }).msg ?? '')
        return field ? `${field}: ${msg}` : msg
      }
      return typeof item === 'string' ? item : null
    })
    .filter((m): m is string => Boolean(m))
  return messages.length ? messages.join('; ') : null
}

function formatRange(period: ReportingPeriod): string {
  return `${period.fiscal_year} (${period.start_date} to ${period.end_date})`
}

export default function NewSubmissionPage({ onCreated, onCancel }: Props) {
  const { token } = useAuth()

  const [options, setOptions] = useState<Options>(EMPTY)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [projectId, setProjectId] = useState('')
  const [periodId, setPeriodId] = useState('')
  const [frameworkId, setFrameworkId] = useState('')
  const [notes, setNotes] = useState('')

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [created, setCreated] = useState<Submission | null>(null)

  useEffect(() => {
    if (!token) return
    let cancelled = false

    Promise.all([
      listProjects(token),
      listReportingPeriods(token),
      listFrameworks(token),
    ])
      .then(([projects, periods, frameworks]) => {
        if (!cancelled) setOptions({ projects, periods, frameworks })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setLoadError(
          err instanceof ApiError
            ? err.message
            : 'Unable to load projects, periods and frameworks.',
        )
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [token])

  const canSubmit = Boolean(projectId && periodId && frameworkId) && !isSubmitting

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!token || !canSubmit) return
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      const submission = await createSubmission(token, {
        project_id: projectId,
        reporting_period_id: periodId,
        framework_id: frameworkId,
        comments: notes.trim() === '' ? null : notes.trim(),
      })
      setCreated(submission)
      onCreated(submission)
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 403) {
          setSubmitError(
            'You do not have permission to file against this project.',
          )
        } else if (err.status === 422 && err.details) {
          setSubmitError(describeValidation(err.details) ?? err.message)
        } else {
          setSubmitError(err.message)
        }
      } else {
        setSubmitError('Could not create the submission. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  if (created) {
    const project = options.projects.find((p) => p.id === created.project_id)
    const period = options.periods.find((p) => p.id === created.reporting_period_id)
    const framework = options.frameworks.find(
      (f) => f.id === created.framework_id,
    )
    return (
      <div className="newsub">
        <div className="newsub-card newsub-card--success">
          <header className="newsub-success">
            <div className="newsub-success-mark">
              <CheckCircle2 size={32} />
            </div>
            <div>
              <span className="newsub-step-badge">Filing Initialised</span>
              <h2 className="newsub-success-title">Submission Successfully Created</h2>
              <p className="newsub-success-sub">
                Your disclosure record is now catalogued in DRAFT status and ready for metric entry.
              </p>
            </div>
          </header>

          <dl className="newsub-summary">
            <div className="newsub-summary-item">
              <dt>Current Status</dt>
              <dd>
                <span className="dash-status-pill dash-status--draft">
                  <span className="dash-status-dot" />
                  <span>{created.status}</span>
                </span>
              </dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Submission UUID</dt>
              <dd className="newsub-mono">{created.id}</dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Reporting Site</dt>
              <dd className="font-semibold">{project?.name ?? created.project_id}</dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Reporting Period</dt>
              <dd>
                <span className="dash-period-badge">
                  {period?.fiscal_year ?? created.reporting_period_id}
                </span>
              </dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Framework Standard</dt>
              <dd>
                {framework
                  ? `${framework.name} v${framework.version}`
                  : created.framework_id}
              </dd>
            </div>
            {created.comments && (
              <div className="newsub-summary-item">
                <dt>Internal Notes</dt>
                <dd>{created.comments}</dd>
              </div>
            )}
          </dl>

          <div className="newsub-hint-box">
            <Sparkles size={16} className="newsub-hint-icon" />
            <p className="newsub-hint">
              You can now locate this submission in your dashboard table and click <strong>Open form</strong> to enter principle-by-principle quantitative and qualitative responses.
            </p>
          </div>

          <div className="newsub-actions-row">
            <button className="newsub-primary" type="button" onClick={onCancel}>
              <span>Return to Dashboard</span>
              <ArrowRight size={15} />
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="newsub">
      <div className="newsub-card">
        <header className="newsub-head">
          <div>
            <div className="newsub-step-badge">
              <ClipboardCheck size={13} />
              <span>Initiate Disclosure Cycle</span>
            </div>
            <h2 className="newsub-title">Create New BRSR Submission</h2>
            <p className="newsub-sub">
              Assign a facility project, select compliance timeframe, and bind a SEBI reporting framework standard.
            </p>
          </div>
          <button className="newsub-ghost" type="button" onClick={onCancel}>
            <X size={15} />
            <span>Cancel</span>
          </button>
        </header>

        {loadError && (
          <div className="newsub-alert" role="alert">
            <AlertTriangle size={16} />
            <span>{loadError}</span>
          </div>
        )}

        <form className="newsub-form" onSubmit={handleSubmit} noValidate>
          {submitError && (
            <div className="newsub-alert" role="alert">
              <AlertTriangle size={16} />
              <span>{submitError}</span>
            </div>
          )}

          <Select
            id="project"
            label="Operating Project / Facility"
            icon={<Building2 size={14} />}
            isLoading={isLoading}
            isEmpty={!isLoading && options.projects.length === 0}
            emptyMessage="No facilities or projects found within authorized scope."
            value={projectId}
            onChange={setProjectId}
            disabled={isSubmitting}
            options={options.projects.map((p) => ({
              value: p.id,
              label: p.code ? `${p.name} (${p.code})` : p.name,
            }))}
          />

          <Select
            id="period"
            label="Reporting Compliance Period"
            icon={<Calendar size={14} />}
            isLoading={isLoading}
            isEmpty={!isLoading && options.periods.length === 0}
            emptyMessage="No reporting periods currently active."
            value={periodId}
            onChange={setPeriodId}
            disabled={isSubmitting}
            options={options.periods.map((p) => ({
              value: p.id,
              label: formatRange(p),
            }))}
          />

          <Select
            id="framework"
            label="BRSR Framework Standard"
            icon={<BookOpen size={14} />}
            isLoading={isLoading}
            isEmpty={!isLoading && options.frameworks.length === 0}
            emptyMessage="No BRSR framework standards registered."
            value={frameworkId}
            onChange={setFrameworkId}
            disabled={isSubmitting}
            options={options.frameworks.map((f) => ({
              value: f.id,
              label: `${f.name} v${f.version}`,
            }))}
          />

          <div className="newsub-field">
            <div className="newsub-label-row">
              <label className="newsub-label" htmlFor="notes">
                <FileText size={14} />
                <span>Internal Audit Notes</span>
              </label>
              <span className="newsub-optional">optional</span>
            </div>
            <textarea
              className="newsub-textarea"
              id="notes"
              rows={3}
              placeholder="Provide contextual comments, site scope references, or prep instructions…"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={isSubmitting}
            />
          </div>

          <div className="newsub-footer-actions">
            <button
              className="newsub-secondary"
              type="button"
              onClick={onCancel}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button className="newsub-primary" type="submit" disabled={!canSubmit}>
              {isSubmitting ? (
                <>
                  <span className="login-spinner" style={{ width: '15px', height: '15px' }} />
                  <span>Creating Filing…</span>
                </>
              ) : (
                <>
                  <span>Create Submission Filing</span>
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function Select({
  id,
  label,
  icon,
  value,
  onChange,
  options,
  isLoading,
  isEmpty,
  emptyMessage,
  disabled,
}: {
  id: string
  label: string
  icon?: React.ReactNode
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
  isLoading: boolean
  isEmpty: boolean
  emptyMessage: string
  disabled: boolean
}) {
  return (
    <div className="newsub-field">
      <label className="newsub-label" htmlFor={id}>
        {icon}
        <span>{label}</span>
      </label>
      <div className="newsub-select-wrap">
        <select
          className="newsub-select"
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          disabled={disabled || isLoading || isEmpty}
        >
          <option value="">
            {isLoading
              ? 'Loading available options…'
              : isEmpty
                ? emptyMessage
                : '— Please choose an option —'}
          </option>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

