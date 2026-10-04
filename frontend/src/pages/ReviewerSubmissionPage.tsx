import { useCallback, useEffect, useState } from 'react'

import type {
  BrsrFrameworkDetail,
  BrsrIndicator,
  BrsrQuestion,
  Evidence,
  Project,
  ReportingPeriod,
  Submission,
  SubmissionValue,
  SubmissionWorkflowResponse,
} from '../api/client'
import {
  ApiError,
  getFramework,
  getSubmission,
  listEvidence,
  listProjects,
  listReportingPeriods,
  listSubmissionValues,
  listWorkflow,
  partitionIndicators,
  requestCorrection,
  reviewSubmission,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './ReviewerSubmissionPage.css'

interface Props {
  submissionId: string
  onClose: () => void
}

interface Loaded {
  submission: Submission
  framework: BrsrFrameworkDetail
  /** Saved answers indexed by question_id. */
  values: Record<string, SubmissionValue>
  /** Evidence indexed by question_id, resolved via submission_value_id. */
  evidence: Record<string, Evidence[]>
  workflow: SubmissionWorkflowResponse[]
  projects: Project[]
  periods: ReportingPeriod[]
}

/** Statuses the backend will move to UNDER_REVIEW. */
const REVIEWABLE = new Set(['SUBMITTED', 'RESUBMITTED'])

function formatBytes(bytes: number | null): string {
  if (bytes === null) return 'Size unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString()
}

/** The answer as a display string; TABLE answers are shown as JSON. */
function answerText(q: BrsrQuestion, v: SubmissionValue | undefined): string {
  if (!v) return ''
  if (q.response_type === 'NUMBER') {
    return v.value_numeric === null ? '' : String(v.value_numeric)
  }
  if (q.response_type === 'TABLE') {
    if (v.value_json) return JSON.stringify(v.value_json)
    return v.value_text ?? ''
  }
  return v.value_text ?? ''
}

/** Evidence is keyed by submission_value_id, so resolve it through the values. */
function groupEvidence(
  evidence: Evidence[],
  values: SubmissionValue[],
): Record<string, Evidence[]> {
  const questionByValue = new Map<string, string>()
  for (const v of values) questionByValue.set(v.id, v.question_id)
  const out: Record<string, Evidence[]> = {}
  for (const e of evidence) {
    if (!e.submission_value_id) continue
    const qid = questionByValue.get(e.submission_value_id)
    if (!qid) continue
    ;(out[qid] ??= []).push(e)
  }
  return out
}

export default function ReviewerSubmissionPage({
  submissionId,
  onClose,
}: Props) {
  const { token } = useAuth()
  const [data, setData] = useState<Loaded | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [reason, setReason] = useState('')
  const [showReason, setShowReason] = useState(false)
  const [reasonError, setReasonError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  /** Load everything the reviewer needs. Read-only calls only. */
  const load = useCallback(async () => {
    if (!token) return
    setIsLoading(true)
    try {
      const sub = await getSubmission(submissionId, token)
      const [framework, values, evidence, workflow, projects, periods] =
        await Promise.all([
          getFramework(sub.framework_id, token),
          listSubmissionValues(submissionId, token),
          listEvidence(submissionId, token),
          listWorkflow(submissionId, token),
          listProjects(token),
          listReportingPeriods(token),
        ])
      setData({
        submission: sub,
        framework,
        values: Object.fromEntries(values.map((v) => [v.question_id, v])),
        evidence: groupEvidence(evidence, values),
        workflow, // already oldest-first from the API
        projects,
        periods,
      })
      setError(null)
    } catch (err) {
      setError(describe(err, 'Could not load this submission.'))
    } finally {
      setIsLoading(false)
    }
  }, [token, submissionId])

  useEffect(() => {
    void load()
  }, [load])

  async function runAction(action: 'review' | 'correction') {
    if (!token || !data || busy) return
    if (action === 'correction' && reason.trim() === '') {
      // The backend rejects blank input with a 400; block it before sending.
      setReasonError('Enter a reason for the correction.')
      return
    }
    setBusy(true)
    setActionError(null)
    setNotice(null)
    setReasonError(null)
    try {
      if (action === 'review') {
        await reviewSubmission(submissionId, null, token)
        setNotice('Review started. The submission is now under review.')
      } else {
        await requestCorrection(submissionId, reason.trim(), token)
        setNotice('Correction requested. The submission was sent back.')
        setReason('')
        setShowReason(false)
      }
      await load()
    } catch (err) {
      setActionError(describe(err, 'The action could not be completed.'))
    } finally {
      setBusy(false)
    }
  }

  if (isLoading) {
    return (
      <div className="rvp">
        <p className="rvp-loading">Loading submission…</p>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="rvp">
        <div className="rvp-alert" role="alert">
          {error ?? 'Submission not found.'}
        </div>
        <button className="rvp-ghost" type="button" onClick={onClose}>
          Back to dashboard
        </button>
      </div>
    )
  }

  const { submission, framework, values, evidence, workflow, projects, periods } =
    data
  const project = projects.find((p) => p.id === submission.project_id)
  const period = periods.find((p) => p.id === submission.reporting_period_id)
  const canReview = REVIEWABLE.has(submission.status)
  const canCorrect = submission.status === 'UNDER_REVIEW'
  // REVIEWER holds only submission:read + submission:review, so there is
  // deliberately no Approve control anywhere in this view.

  return (
    <div className="rvp">
      <header className="rvp-head">
        <div>
          <h2 className="rvp-title">{framework.name}</h2>
          <p className="rvp-sub">
            v{framework.version} · read-only review view
          </p>
        </div>
        <button className="rvp-ghost" type="button" onClick={onClose}>
          Close
        </button>
      </header>

      <section className="rvp-summary">
        <span className={`rvp-status rvp-status--${submission.status.toLowerCase()}`}>
          {submission.status.replace(/_/g, ' ')}
        </span>
        <dl className="rvp-facts">
          <div>
            <dt>Project</dt>
            <dd>
              {project
                ? `${project.name}${project.code ? ` (${project.code})` : ''}`
                : submission.project_id}
            </dd>
          </div>
          <div>
            <dt>Reporting period</dt>
            <dd>
              {period ? period.fiscal_year : submission.reporting_period_id}
            </dd>
          </div>
          <div>
            <dt>Framework</dt>
            <dd>
              {framework.name} v{framework.version}
            </dd>
          </div>
        </dl>
      </section>

      {notice && (
        <p className="rvp-ok" role="status">
          {notice}
        </p>
      )}
      {actionError && (
        <p className="rvp-alert" role="alert">
          {actionError}
        </p>
      )}

      {(canReview || canCorrect) && (
        <div className="rvp-actions">
          {canReview && (
            <button
              className="rvp-action"
              type="button"
              disabled={busy}
              onClick={() => runAction('review')}
            >
              {busy ? 'Working…' : 'Start Review'}
            </button>
          )}
          {canCorrect && !showReason && (
            <button
              className="rvp-action rvp-action--warn"
              type="button"
              disabled={busy}
              onClick={() => {
                setShowReason(true)
                setReasonError(null)
              }}
            >
              Request Correction
            </button>
          )}
        </div>
      )}

      {canCorrect && showReason && (
        <div className="rvp-reason">
          <label className="rvp-reason-label" htmlFor="rvp-reason">
            Reason for correction <span className="rvp-req">required</span>
          </label>
          <textarea
            className="rvp-reason-input"
            id="rvp-reason"
            rows={3}
            value={reason}
            disabled={busy}
            placeholder="Describe what must be corrected"
            onChange={(e) => {
              setReason(e.target.value)
              if (reasonError) setReasonError(null)
            }}
          />
          {reasonError && (
            <p className="rvp-reason-err" role="alert">
              {reasonError}
            </p>
          )}
          <div className="rvp-reason-actions">
            <button
              className="rvp-action rvp-action--warn"
              type="button"
              disabled={busy}
              onClick={() => runAction('correction')}
            >
              {busy ? 'Sending…' : 'Send correction request'}
            </button>
            <button
              className="rvp-ghost"
              type="button"
              disabled={busy}
              onClick={() => {
                setShowReason(false)
                setReasonError(null)
              }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <ReviewerBody framework={framework} values={values} evidence={evidence} />

      <section className="rvp-timeline">
        <h3 className="rvp-timeline-title">Workflow history</h3>
        {workflow.length === 0 ? (
          <p className="rvp-empty">No transitions recorded yet.</p>
        ) : (
          <ol className="rvp-timeline-list">
            {workflow.map((w) => (
              <li className="rvp-timeline-item" key={w.id}>
                <span className="rvp-timeline-move">
                  {w.from_status.replace(/_/g, ' ')} → {w.to_status.replace(/_/g, ' ')}
                </span>
                <span className="rvp-timeline-when">{formatDate(w.created_at)}</span>
                {w.comments && (
                  <span className="rvp-timeline-note">“{w.comments}”</span>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  )
}

function describe(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 404) return 'That submission no longer exists.'
    return err.message
  }
  return fallback
}

/** Read-only Section -> Principle -> Indicator -> Question rendering. */
function ReviewerBody({
  framework,
  values,
  evidence,
}: {
  framework: BrsrFrameworkDetail
  values: Record<string, SubmissionValue>
  evidence: Record<string, Evidence[]>
}) {
  return (
    <div className="rvp-body">
      {framework.sections.map((section) => {
        // Same verified partition as the editable form: section.indicators is
        // a superset, so take only principle_id-null ones here.
        const { loose } = partitionIndicators(section)
        return (
          <section className="rvp-section" key={section.id}>
            <h3 className="rvp-section-title">
              {section.code} · {section.title}
            </h3>

            {loose.map((indicator) => (
              <IndicatorBlock
                key={indicator.id}
                indicator={indicator}
                values={values}
                evidence={evidence}
              />
            ))}

            {section.principles.map((principle) => (
              <div className="rvp-principle" key={principle.id}>
                <h4 className="rvp-principle-title">
                  Principle {principle.principle_number} · {principle.title}
                </h4>
                {principle.indicators.map((indicator) => (
                  <IndicatorBlock
                    key={indicator.id}
                    indicator={indicator}
                    values={values}
                    evidence={evidence}
                  />
                ))}
              </div>
            ))}
          </section>
        )
      })}
    </div>
  )
}

function IndicatorBlock({
  indicator,
  values,
  evidence,
}: {
  indicator: BrsrIndicator
  values: Record<string, SubmissionValue>
  evidence: Record<string, Evidence[]>
}) {
  const essential = indicator.indicator_type === 'ESSENTIAL'
  return (
    <article className="rvp-indicator">
      <header className="rvp-indicator-head">
        <h5 className="rvp-indicator-title">{indicator.title}</h5>
        <span className={essential ? 'rvp-tag rvp-tag--ess' : 'rvp-tag rvp-tag--lead'}>
          {essential ? 'Essential' : 'Leadership'}
        </span>
      </header>
      <p className="rvp-indicator-code">{indicator.code}</p>

      {indicator.questions.map((question) => {
        const value = values[question.id]
        const text = answerText(question, value)
        const files = evidence[question.id] ?? []
        return (
          <div className="rvp-question" key={question.id}>
            <p className="rvp-q-label">
              <span className="rvp-q-code">{question.code}</span>
              <span className="rvp-q-text">{question.question_text}</span>
              {question.is_mandatory && <span className="rvp-req">required</span>}
            </p>
            <p className={value ? 'rvp-answer' : 'rvp-answer rvp-answer--empty'}>
              {value ? text || '(no value recorded)' : 'Not answered'}
            </p>

            {files.length > 0 && (
              <ul className="rvp-ev">
                {files.map((f) => (
                  <li className="rvp-ev-item" key={f.id}>
                    <span className="rvp-ev-name">{f.file_name}</span>
                    <span className="rvp-ev-meta">
                      {formatBytes(f.file_size_bytes)}
                      {f.content_type ? ` · ${f.content_type}` : ''}
                      {f.created_at ? ` · ${formatDate(f.created_at)}` : ''}
                    </span>
                    {f.description && (
                      <span className="rvp-ev-desc">{f.description}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )
      })}
    </article>
  )
}