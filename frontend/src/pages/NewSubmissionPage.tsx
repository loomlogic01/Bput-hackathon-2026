import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'

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
        <div className="newsub-card">
          <header className="newsub-success">
            <span className="newsub-success-mark">OK</span>
            <div>
              <h2 className="newsub-success-title">Submission created</h2>
              <p className="newsub-success-sub">
                A new submission is ready for data entry.
              </p>
            </div>
          </header>

          <dl className="newsub-summary">
            <div className="newsub-summary-item">
              <dt>Status</dt>
              <dd>
                <span className="newsub-status">{created.status}</span>
              </dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Submission ID</dt>
              <dd className="newsub-mono">{created.id}</dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Project</dt>
              <dd>{project?.name ?? created.project_id}</dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Reporting period</dt>
              <dd>{period?.fiscal_year ?? created.reporting_period_id}</dd>
            </div>
            <div className="newsub-summary-item">
              <dt>Framework</dt>
              <dd>
                {framework
                  ? `${framework.name} v${framework.version}`
                  : created.framework_id}
              </dd>
            </div>
            {created.comments && (
              <div className="newsub-summary-item">
                <dt>Notes</dt>
                <dd>{created.comments}</dd>
              </div>
            )}
          </dl>

          <p className="newsub-hint">
            The BRSR question form is the next milestone. This submission is
            currently empty and in DRAFT.
          </p>
          <button className="newsub-primary" type="button" onClick={onCancel}>
            Back to dashboard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="newsub">
      <div className="newsub-card">
        <header className="newsub-head">
          <div>
            <h2 className="newsub-title">New Submission</h2>
            <p className="newsub-sub">
              Choose the project, reporting period and BRSR framework.
            </p>
          </div>
          <button className="newsub-ghost" type="button" onClick={onCancel}>
            Cancel
          </button>
        </header>

        {loadError && (
          <div className="newsub-alert" role="alert">
            {loadError}
          </div>
        )}

        <form className="newsub-form" onSubmit={handleSubmit} noValidate>
          {submitError && (
            <div className="newsub-alert" role="alert">
              {submitError}
            </div>
          )}

          <Select
            id="project"
            label="Project"
            isLoading={isLoading}
            isEmpty={!isLoading && options.projects.length === 0}
            emptyMessage="No projects are available in your scope."
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
            label="Reporting period"
            isLoading={isLoading}
            isEmpty={!isLoading && options.periods.length === 0}
            emptyMessage="No reporting periods are available."
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
            label="BRSR framework"
            isLoading={isLoading}
            isEmpty={!isLoading && options.frameworks.length === 0}
            emptyMessage="No BRSR frameworks are available."
            value={frameworkId}
            onChange={setFrameworkId}
            disabled={isSubmitting}
            options={options.frameworks.map((f) => ({
              value: f.id,
              label: `${f.name} v${f.version}`,
            }))}
          />

          <div className="newsub-field">
            <label className="newsub-label" htmlFor="notes">
              Notes <span className="newsub-optional">optional</span>
            </label>
            <textarea
              className="newsub-textarea"
              id="notes"
              rows={3}
              placeholder="Internal notes about this submission"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              disabled={isSubmitting}
            />
          </div>

          <button className="newsub-primary" type="submit" disabled={!canSubmit}>
            {isSubmitting ? 'Creating…' : 'Create submission'}
          </button>
        </form>
      </div>
    </div>
  )
}

function Select({
  id,
  label,
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
        {label}
      </label>
      <select
        className="newsub-select"
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled || isLoading || isEmpty}
      >
        <option value="">
          {isLoading
            ? 'Loading…'
            : isEmpty
              ? emptyMessage
              : 'Please select…'}
        </option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  )
}
