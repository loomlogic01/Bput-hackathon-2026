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
  AlertCircle,
  ArrowLeft,
  Building2,
  Calendar,
  CheckCircle2,
  Clock,
  FileText,
  History,
  Lock,
  Paperclip,
  ShieldCheck,
} from 'lucide-react'
import {
  ApiError,
  approveSubmission,
  getFramework,
  getSubmission,
  listEvidence,
  listProjects,
  listReportingPeriods,
  listSubmissionValues,
  listWorkflow,
  lockSubmission,
  partitionIndicators,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './ApproverSubmissionPage.css'

interface Props {
  submissionId: string
  onClose: () => void
}

interface Loaded {
  submission: Submission
  framework: BrsrFrameworkDetail
  /** Saved answers indexed by question_id. */
  values: Record<string, SubmissionValue>
  /**
   * Evidence indexed by question_id, resolved via submission_value_id, plus the
   * '' key for files attached at submission level rather than to one answer.
   */
  evidence: Record<string, Evidence[]>
  workflow: SubmissionWorkflowResponse[]
  projects: Project[]
  periods: ReportingPeriod[]
}

/** Statuses the backend will move to APPROVED. */
const APPROVABLE = new Set(['UNDER_REVIEW', 'RESUBMITTED'])
/** Statuses the backend will move to LOCKED. */
const LOCKABLE = new Set(['APPROVED'])

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
    if (v.value_json) return JSON.stringify(v.value_json, null, 2)
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
  const out: Record<string, Evidence[]> = { '': [] }
  for (const e of evidence) {
    if (!e.submission_value_id) {
      out[''].push(e)
      continue
    }
    const qid = questionByValue.get(e.submission_value_id)
    if (!qid) continue
    ;(out[qid] ??= []).push(e)
  }
  if (out[''].length === 0) delete out['']
  return out
}

/** Turn a rejected transition into a message an approver can act on. */
function actionErrorMessage(err: unknown, verb: string): string {
  if (err instanceof ApiError) {
    if (err.status === 403)
      return 'You do not have permission to perform this action. An APPROVER role is required.'
    if (err.status === 401) return 'Your session has expired. Please sign in again.'
    if (err.status === 404) return 'This submission no longer exists.'
    if (err.status === 422) return 'The request was rejected as invalid.'
    return err.message || `Unable to ${verb}.`
  }
  return `Unable to ${verb}.`
}

export default function ApproverSubmissionPage({
  submissionId,
  onClose,
}: Props) {
  const { token } = useAuth()
  const [data, setData] = useState<Loaded | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [comments, setComments] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  /**
   * Load everything the approver needs. Every call here is read-only.
   */
  const load = useCallback(async () => {
    if (!token) return
    setIsLoading(true)
    setError(null)
    try {
      const [submission, projects, periods] = await Promise.all([
        getSubmission(submissionId, token),
        listProjects(token),
        listReportingPeriods(token),
      ])
      const [framework, values, evidence, workflow] = await Promise.all([
        getFramework(submission.framework_id, token),
        listSubmissionValues(submissionId, token),
        listEvidence(submissionId, token),
        listWorkflow(submissionId, token),
      ])
      const byQuestion: Record<string, SubmissionValue> = {}
      for (const v of values) byQuestion[v.question_id] = v
      setData({
        submission,
        framework,
        values: byQuestion,
        evidence: groupEvidence(evidence, values),
        workflow,
        projects,
        periods,
      })
    } catch (err) {
      setData(null)
      if (err instanceof ApiError) {
        setError(
          err.status === 401
            ? 'Your session has expired. Please sign in again.'
            : err.message,
        )
      } else {
        setError('Unable to load this submission.')
      }
    } finally {
      setIsLoading(false)
    }
  }, [submissionId, token])

  useEffect(() => {
    void load()
  }, [load])

  const status = data?.submission.status ?? null
  const canApprove = status !== null && APPROVABLE.has(status)
  const canLock = status !== null && LOCKABLE.has(status)

  /** Shared path for both actions: confirm, call, then re-read from the server. */
  const runAction = useCallback(
    async (
      verb: 'approve' | 'lock',
      confirmText: string,
      successText: string,
    ) => {
      if (!token) return
      if (!window.confirm(confirmText)) return

      setBusy(true)
      setActionError(null)
      setNotice(null)
      try {
        const trimmed = comments.trim()
        const comment = trimmed === '' ? undefined : trimmed
        if (verb === 'approve') {
          await approveSubmission(submissionId, comment, token)
        } else {
          await lockSubmission(submissionId, comment, token)
        }
        setComments('')
        setNotice(successText)
        await load()
      } catch (err) {
        setActionError(actionErrorMessage(err, verb))
      } finally {
        setBusy(false)
      }
    },
    [comments, load, submissionId, token],
  )

  if (isLoading) {
    return (
      <div className="avp">
        <div className="avp-loading">
          <div className="avp-spinner" />
          <p>Loading submission for executive review…</p>
        </div>
      </div>
    )
  }

  if (error !== null || data === null) {
    return (
      <div className="avp">
        <div className="avp-alert" role="alert">
          <AlertCircle size={18} />
          <span>{error ?? 'Unable to load this submission.'}</span>
        </div>
        <button className="avp-ghost" type="button" onClick={onClose}>
          <ArrowLeft size={16} /> Back to dashboard
        </button>
      </div>
    )
  }

  const { submission, framework, values, evidence, workflow, projects, periods } =
    data

  const projectName =
    projects.find((p) => p.id === submission.project_id)?.name ?? '—'
  const periodLabel =
    submission.reporting_period_label ??
    periods.find((p) => p.id === submission.reporting_period_id)?.fiscal_year ??
    '—'
  const looseFiles = evidence[''] ?? []

  return (
    <div className="avp">
      {/* Header */}
      <header className="avp-head">
        <div>
          <button className="avp-back-btn" type="button" onClick={onClose}>
            <ArrowLeft size={16} /> Back to Dashboard
          </button>
          <div className="avp-title-wrap">
            <h2 className="avp-title">{framework.name}</h2>
            <span className="avp-version-badge">v{framework.version}</span>
            <span className="avp-mode-pill">
              <ShieldCheck size={14} /> Approver Mode
            </span>
          </div>
          <p className="avp-sub">
            Executive approval portal. Review all responses, audit trails, and certify or lock the filing.
          </p>
        </div>
      </header>

      {/* Notifications */}
      {actionError !== null && (
        <div className="avp-alert" role="alert">
          <AlertCircle size={18} />
          <span>{actionError}</span>
        </div>
      )}
      {notice !== null && (
        <div className="avp-ok" role="status">
          <CheckCircle2 size={18} />
          <span>{notice}</span>
        </div>
      )}

      {/* Summary Card */}
      <section className="avp-summary-card">
        <div className="avp-summary-main">
          <div className="avp-summary-item">
            <span className="avp-item-label">
              <Building2 size={13} /> Project
            </span>
            <span className="avp-item-val">{projectName}</span>
          </div>
          <div className="avp-summary-item">
            <span className="avp-item-label">
              <Calendar size={13} /> Reporting Period
            </span>
            <span className="avp-item-val">{periodLabel}</span>
          </div>
          <div className="avp-summary-item">
            <span className="avp-item-label">
              <FileText size={13} /> Framework
            </span>
            <span className="avp-item-val">{framework.name}</span>
          </div>
          <div className="avp-summary-item">
            <span className="avp-item-label">
              <Clock size={13} /> Last Updated
            </span>
            <span className="avp-item-val">
              {formatDate(submission.updated_at ?? submission.created_at)}
            </span>
          </div>
        </div>
        <div className="avp-summary-status">
          <span className="avp-item-label">Status</span>
          <span className={`avp-status avp-status--${submission.status.toLowerCase()}`}>
            <span className="avp-status-dot" />
            {submission.status.replace(/_/g, ' ')}
          </span>
        </div>
      </section>

      {/* Approval / Lock Actions */}
      <section className="avp-actions-card" aria-label="Approval actions">
        <div className="avp-actions-header">
          <h3 className="avp-actions-title">Executive Decision</h3>
          <p className="avp-actions-desc">
            {canApprove && 'This submission is ready for executive approval and sign-off.'}
            {canLock && 'This submission has been approved and may now be locked permanently against further edits.'}
            {!canApprove && !canLock && (
              submission.status === 'LOCKED'
                ? 'This submission has been locked. The filing is finalized and read-only.'
                : 'No approval actions are available for this submission at its current stage.'
            )}
          </p>
        </div>

        {canApprove && (
          <div className="avp-decision-body">
            <label className="avp-label" htmlFor="avp-comments">
              Approval Note / Remarks (optional)
            </label>
            <textarea
              id="avp-comments"
              className="avp-textarea"
              rows={3}
              value={comments}
              placeholder="Add an optional comment for the audit trail before approving…"
              onChange={(e) => setComments(e.target.value)}
            />
            <button
              className="avp-action-btn avp-action-btn--approve"
              type="button"
              disabled={busy}
              onClick={() =>
                void runAction(
                  'approve',
                  'Approve this submission? This will be recorded permanently in the audit trail.',
                  'Submission successfully approved.',
                )
              }
            >
              <CheckCircle2 size={16} />
              {busy ? 'Processing…' : 'Approve Submission'}
            </button>
          </div>
        )}

        {canLock && (
          <div className="avp-decision-body">
            <label className="avp-label" htmlFor="avp-lock-comments">
              Locking Remarks (optional)
            </label>
            <textarea
              id="avp-lock-comments"
              className="avp-textarea"
              rows={3}
              value={comments}
              placeholder="Add an optional comment for the audit trail before locking…"
              onChange={(e) => setComments(e.target.value)}
            />
            <button
              className="avp-action-btn avp-action-btn--lock"
              type="button"
              disabled={busy}
              onClick={() =>
                void runAction(
                  'lock',
                  'Lock this submission? Locking is final and cannot be undone.',
                  'Submission successfully locked.',
                )
              }
            >
              <Lock size={16} />
              {busy ? 'Processing…' : 'Lock Submission (Final)'}
            </button>
          </div>
        )}
      </section>
      {/* ── Workflow history, oldest first ── */}
      <section className="avp-timeline">
        <div className="avp-timeline-head">
          <History size={18} />
          <h3 className="avp-timeline-title">Workflow Audit History</h3>
        </div>
        {workflow.length === 0 ? (
          <p className="avp-empty">No transitions recorded yet.</p>
        ) : (
          <ol className="avp-timeline-list">
            {workflow.map((row) => (
              <li className="avp-timeline-item" key={row.id}>
                <div className="avp-timeline-marker" />
                <div className="avp-timeline-content">
                  <div className="avp-timeline-row">
                    <span className="avp-timeline-move">
                      {row.from_status.replace(/_/g, ' ')} →{' '}
                      {row.to_status.replace(/_/g, ' ')}
                    </span>
                    <span className="avp-timeline-when">
                      <Clock size={12} /> {formatDate(row.created_at)}
                    </span>
                  </div>
                  {row.comments && (
                    <div className="avp-timeline-note">“{row.comments}”</div>
                  )}
                </div>
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* ── Evidence attached at submission level ── */}
      {looseFiles.length > 0 && (
        <section className="avp-loose-docs">
          <div className="avp-loose-head">
            <Paperclip size={16} />
            <h4 className="avp-loose-title">Supporting Documents (Submission Level)</h4>
          </div>
          <ul className="avp-ev">
            {looseFiles.map((f) => (
              <li className="avp-ev-item" key={f.id}>
                <span className="avp-ev-name">
                  <Paperclip size={13} className="avp-ev-icon" />
                  {f.file_name}
                </span>
                <span className="avp-ev-meta">
                  {formatBytes(f.file_size_bytes)}
                  {f.content_type ? ` · ${f.content_type}` : ''}
                  {f.created_at ? ` · ${formatDate(f.created_at)}` : ''}
                </span>
                {f.description && (
                  <span className="avp-ev-desc">{f.description}</span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* ── BRSR questions and saved answers, read-only ── */}
      <h4 className="avp-section-title">BRSR responses</h4>
      <div className="avp-body">
        {framework.sections.map((section) => {
          // As in the editable form: section.indicators is a superset, so take
          // only principle_id-null ones here.
          const { loose } = partitionIndicators(section)
          return (
            <section className="avp-section" key={section.id}>
              <h5 className="avp-section-head">
                {section.code} · {section.title}
              </h5>

              {loose.map((indicator) => (
                <IndicatorBlock
                  key={indicator.id}
                  indicator={indicator}
                  values={values}
                  evidence={evidence}
                />
              ))}

              {section.principles.map((principle) => (
                <div className="avp-principle" key={principle.id}>
                  <h6 className="avp-principle-title">
                    Principle {principle.principle_number} · {principle.title}
                  </h6>
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
    </div>
  )
}

/** Read-only rendering of one indicator: its questions, answers and evidence. */
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
    <article className="avp-indicator">
      <header className="avp-indicator-head">
        <h5 className="avp-indicator-title">{indicator.title}</h5>
        <span
          className={essential ? 'avp-tag avp-tag--ess' : 'avp-tag avp-tag--lead'}
        >
          {essential ? 'Essential' : 'Leadership'}
        </span>
      </header>
      <p className="avp-indicator-code">{indicator.code}</p>

      {indicator.questions.map((question) => {
        const value = values[question.id]
        const text = answerText(question, value)
        const files = evidence[question.id] ?? []
        return (
          <div className="avp-question" key={question.id}>
            <p className="avp-q-label">
              <span className="avp-q-code">{question.code}</span>
              <span className="avp-q-text">{question.question_text}</span>
              {question.is_mandatory && <span className="avp-req">required</span>}
            </p>
            <p className={value ? 'avp-answer' : 'avp-answer avp-answer--empty'}>
              {value ? text || '(no value recorded)' : 'Not answered'}
            </p>

            {files.length > 0 && (
              <div className="avp-ev-wrap">
                <span className="avp-ev-title">Attached Evidence ({files.length}):</span>
                <ul className="avp-ev">
                  {files.map((f) => (
                    <li className="avp-ev-item" key={f.id}>
                      <span className="avp-ev-name">
                        <Paperclip size={13} className="avp-ev-icon" />
                        {f.file_name}
                      </span>
                      <span className="avp-ev-meta">
                        {formatBytes(f.file_size_bytes)}
                        {f.content_type ? ` · ${f.content_type}` : ''}
                        {f.created_at ? ` · ${formatDate(f.created_at)}` : ''}
                      </span>
                      {f.description && (
                        <span className="avp-ev-desc">{f.description}</span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )
      })}
    </article>
  )
}