import { useEffect, useMemo, useRef, useState } from 'react'

import type {
  BrsrFrameworkDetail,
  BrsrIndicator,
  BrsrIndicatorType,
  BrsrQuestion,
  Evidence,
  MissingQuestion,
  Submission,
  SubmissionValue,
} from '../api/client'
import {
  ApiError,
  getFramework,
  getSubmission,
  listEvidence,
  listSubmissionValues,
  partitionIndicators,
  resubmitSubmission,
  saveSubmissionValue,
  submitSubmission,
  uploadEvidence,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './SubmissionFormPage.css'

interface Props {
  submissionId: string
  onClose: () => void
}

type Filter = 'ALL' | BrsrIndicatorType

/** Matches the backend's EDITABLE_STATUSES exactly. */
const EDITABLE = new Set(['DRAFT', 'CORRECTION_REQUIRED'])

/** Per-question save lifecycle. */
type SaveState = 'idle' | 'saving' | 'saved' | 'error'

/** Everything the page mutates after load lives here. */
interface FormState {
  /** Latest server rows, indexed by question_id. */
  values: Record<string, SubmissionValue>
  /** Local edits keyed by question_id, so saving one question never disturbs another. */
  drafts: Record<string, string>
  saveState: Record<string, SaveState>
  message: Record<string, string>
  /** Evidence grouped by question_id. Submission-level files are not surfaced. */
  evidence: Record<string, Evidence[]>
  uploadState: Record<string, SaveState>
  uploadMessage: Record<string, string>
}

/** Outcome of the last "Submit for Review" attempt. */
interface SubmitOutcome {
  isSubmitting: boolean
  /** Set when the API rejected the submit because questions are missing. */
  missing: MissingQuestion[]
  /** The API's message, shown verbatim. */
  message: string
  /** Other (non-validation) failures, e.g. the status guard or a 403. */
  error: string | null
  /** True once a submit has succeeded in this session. */
  succeeded: boolean
}

/** Total questions in a framework, following the verified partition rule. */
function countQuestions(framework: BrsrFrameworkDetail): number {
  return framework.sections.reduce((total, section) => {
    const { loose, nested } = partitionIndicators(section)
    return total + [...loose, ...nested].reduce((n, i) => n + i.questions.length, 0)
  }, 0)
}

/** Every question id in the submission's own framework. */
function questionIds(framework: BrsrFrameworkDetail): Set<string> {
  const ids = new Set<string>()
  for (const section of framework.sections) {
    const { loose, nested } = partitionIndicators(section)
    for (const i of [...loose, ...nested]) {
      for (const q of i.questions) ids.add(q.id)
    }
  }
  return ids
}

/** The saved answer rendered into its control, as a string. */
function serverText(
  question: BrsrQuestion,
  value: SubmissionValue | undefined,
): string {
  if (!value) return ''
  if (question.response_type === 'NUMBER') {
    return value.value_numeric === null ? '' : String(value.value_numeric)
  }
  if (question.response_type === 'TABLE') {
    return value.value_json === null ? '' : JSON.stringify(value.value_json, null, 2)
  }
  return value.value_text ?? ''
}

// SPLIT_A

export default function SubmissionFormPage({
  submissionId,
  onClose,
}: Props) {
  const { token } = useAuth()

  const [submission, setSubmission] = useState<Submission | null>(null)
  const [framework, setFramework] = useState<BrsrFrameworkDetail | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('ALL')
  const [form, setForm] = useState<FormState>({
    values: {},
    drafts: {},
    saveState: {},
    message: {},
    evidence: {},
    uploadState: {},
    uploadMessage: {},
  })
  /** Guards a late response from landing after unmount. */
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true
    return () => {
      mounted.current = false
    }
  }, [])

  useEffect(() => {
    if (!token) return
    // Narrow once: TypeScript does not carry the guard into the closure.
    const authToken = token
    let cancelled = false
    setIsLoading(true)
    setError(null)

    async function load() {
      // Resolve the submission first: it carries the framework_id that
      // selects the hierarchy to load.
      let sub: Submission
      try {
        sub = await getSubmission(submissionId, authToken)
      } catch (err) {
        if (!cancelled) {
          setError(describe(err, 'Could not load this submission.'))
          setIsLoading(false)
        }
        return
      }

      try {
        const [fw, values, evidence] = await Promise.all([
          getFramework(sub.framework_id, authToken),
          listSubmissionValues(submissionId, authToken),
          listEvidence(submissionId, authToken),
        ])
        if (cancelled) return
        setSubmission(sub)
        setFramework(fw)
        setForm({
          values: Object.fromEntries(values.map((v) => [v.question_id, v])),
          drafts: {},
          saveState: {},
          message: {},
          evidence: groupEvidence(evidence, values),
          uploadState: {},
          uploadMessage: {},
        })
      } catch (err) {
        if (!cancelled) setError(describe(err, 'Could not load the BRSR form.'))
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [token, submissionId])

  const readOnly = submission !== null && !EDITABLE.has(submission.status)
  const ownQuestionIds = useMemo(
    () => (framework ? questionIds(framework) : new Set<string>()),
    [framework],
  )

/**
   * Save one question. Always sends the COMPLETE value object, because the
   * API replaces all six columns - a sparse payload would wipe whatever it
   * omits, including the three metadata fields.
   */
  async function saveQuestion(question: BrsrQuestion) {
    if (!token || readOnly) return

    // Framework safety: never post a question outside this submission's own
    // framework, even if something managed to invoke this directly.
    if (!ownQuestionIds.has(question.id)) {
      setForm((f) => ({
        ...f,
        saveState: { ...f.saveState, [question.id]: 'error' },
        message: {
          ...f.message,
          [question.id]: 'This question does not belong to the submission framework.',
        },
      }))
      return
    }

    const existing = form.values[question.id]
    const raw =
      form.drafts[question.id] ?? serverText(question, existing)
    const parsed = toPayload(question, raw)

    if ('error' in parsed) {
      // Rejected client-side; no request is sent.
      setForm((f) => ({
        ...f,
        saveState: { ...f.saveState, [question.id]: 'error' },
        message: { ...f.message, [question.id]: parsed.error },
      }))
      return
    }

    setForm((f) => ({
      ...f,
      saveState: { ...f.saveState, [question.id]: 'saving' },
      message: { ...f.message, [question.id]: '' },
    }))

    try {
      const saved = await saveSubmissionValue(
        submissionId,
        {
          question_id: question.id,
          // Only the field for this response_type is written; the other two go
          // to null explicitly so no stale value from a prior type survives.
          value_text: parsed.value_text,
          value_numeric: parsed.value_numeric,
          value_json: parsed.value_json,
          // Metadata is not editable here, so carry existing values through.
          data_source: existing?.data_source ?? null,
          calculation_method: existing?.calculation_method ?? null,
          source_department: existing?.source_department ?? null,
        },
        token,
      )
      if (!mounted.current) return
      setForm((f) => ({
        ...f,
        // Refreshes the answered count immediately.
        values: { ...f.values, [question.id]: saved },
        // Drop only this question's draft; other unsaved edits are untouched.
        drafts: omit(f.drafts, question.id),
        saveState: { ...f.saveState, [question.id]: 'saved' },
        message: { ...f.message, [question.id]: '' },
      }))
    } catch (err) {
      if (!mounted.current) return
      setForm((f) => ({
        ...f,
        saveState: { ...f.saveState, [question.id]: 'error' },
        message: { ...f.message, [question.id]: describeSave(err) },
      }))
    }
  }

  const [submitOutcome, setSubmitOutcome] = useState<SubmitOutcome>({
    isSubmitting: false,
    missing: [],
    message: '',
    error: null,
    succeeded: false,
  })

  /** Scroll a listed missing question into view and focus it.
   *
   * The anchor is the question ROW, not the control: some response types
   * (BOOLEAN) render a non-focusable div with no id, so a control-only lookup
   * silently failed for them. Missing targets are ignored on purpose.
   */
  function focusQuestion(questionId: string) {
    const el = document.getElementById(`q-${questionId}`)
    if (!el) return
    el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    if (typeof el.focus === 'function') {
      el.focus({ preventScroll: true })
    }
  }

  /**
   * Hand the submission to a reviewer.
   *
   * DRAFT goes through /submit, which validates mandatory questions and can
   * come back with a missing_questions list. CORRECTION_REQUIRED goes through
   * /resubmit, which the backend does NOT validate - deliberately preserved.
   * RESUBMITTED is a distinct status from SUBMITTED and is read-only.
   *
   * Answers are never touched here: on a validation failure the form state is
   * left exactly as it was, so nothing the user has typed is lost.
   */
  async function onSubmit() {
    if (!token || readOnly || submitOutcome.isSubmitting) return
    // Never hand over while an answer save is still in flight.
    if (Object.values(form.saveState).some((s) => s === 'saving')) return

    const isCorrection = submission?.status === 'CORRECTION_REQUIRED'
    const answered = Object.keys(form.values).length
    const confirmed = window.confirm(
      isCorrection
        ? `Resubmit this submission for review?\n\n` +
            `${answered} of ${framework ? countQuestions(framework) : answered} ` +
            `questions answered.\n\n` +
            `Once resubmitted you cannot edit it until a reviewer responds.`
        : `Submit this submission for review?\n\n` +
            `${answered} of ${framework ? countQuestions(framework) : answered} ` +
            `questions answered.\n\n` +
            `Once submitted you cannot edit it until a reviewer requests corrections.`,
    )
    if (!confirmed) return

    setSubmitOutcome((o) => ({
      ...o,
      isSubmitting: true,
      missing: [],
      message: '',
      error: null,
    }))

    try {
      if (isCorrection) {
        // Comments are optional on this transition; send an explicit null.
        await resubmitSubmission(submissionId, null, token)
      } else {
        await submitSubmission(submissionId, token)
      }
      if (!mounted.current) return
      // Re-read the submission so the displayed status is the server's truth;
      // readOnly then follows automatically (neither SUBMITTED nor RESUBMITTED
      // is in EDITABLE).
      const fresh = await getSubmission(submissionId, token)
      if (!mounted.current) return
      setSubmission(fresh)
      setSubmitOutcome({
        isSubmitting: false,
        missing: [],
        message: isCorrection
          ? 'Resubmitted for review.'
          : 'Submission submitted for review.',
        error: null,
        succeeded: true,
      })
    } catch (err) {
      if (!mounted.current) return
      if (err instanceof ApiError && err.status === 400 && err.objectDetail) {
        const raw = err.objectDetail.missing_questions
        const missing: MissingQuestion[] = Array.isArray(raw)
          ? (raw as MissingQuestion[])
          : []
        setSubmitOutcome({
          isSubmitting: false,
          missing,
          message:
            typeof err.objectDetail.message === 'string'
              ? err.objectDetail.message
              : err.message,
          error: null,
          succeeded: false,
        })
      } else {
        setSubmitOutcome({
          isSubmitting: false,
          missing: [],
          message: '',
          error: describeSave(err),
          succeeded: false,
        })
      }
    }
  }

  function onEdit(questionId: string, next: string) {
    setForm((f) => ({
      ...f,
      drafts: { ...f.drafts, [questionId]: next },
      saveState: { ...f.saveState, [questionId]: 'idle' },
      message: { ...f.message, [questionId]: '' },
    }))
  }

  /**
   * Attach a file to a question's saved answer.
   *
   * The API expects the SubmissionValue id in `submission_value_id`, so this
   * only works once the answer has been saved - the control is not rendered
   * until `savedValue` exists. Never send a question id here.
   */
  async function onUploadEvidence(
    question: BrsrQuestion,
    file: File,
    description: string,
  ) {
    if (!token || readOnly) return
    const savedValue = form.values[question.id]
    if (!savedValue) return

    setForm((f) => ({
      ...f,
      uploadState: { ...f.uploadState, [question.id]: 'saving' },
      uploadMessage: { ...f.uploadMessage, [question.id]: '' },
    }))

    try {
      const created = await uploadEvidence(
        submissionId,
        file,
        {
          description: description.trim() === '' ? undefined : description.trim(),
          submissionValueId: savedValue.id,
        },
        token,
      )
      if (!mounted.current) return
      setForm((f) => ({
        ...f,
        evidence: {
          ...f.evidence,
          [question.id]: [...(f.evidence[question.id] ?? []), created],
        },
        uploadState: { ...f.uploadState, [question.id]: 'saved' },
        uploadMessage: { ...f.uploadMessage, [question.id]: '' },
      }))
    } catch (err) {
      if (!mounted.current) return
      setForm((f) => ({
        ...f,
        uploadState: { ...f.uploadState, [question.id]: 'error' },
        uploadMessage: { ...f.uploadMessage, [question.id]: describeUpload(err) },
      }))
    }
  }

  const sections = useMemo(() => {
    if (!framework) return []
    return framework.sections.map((section) => {
      const { loose } = partitionIndicators(section)
      return {
        section,
        // loose indicators sit directly under the section; nested ones are
        // rendered inside their own principle. Never both from section.indicators.
        loose: loose.filter(matches(filter)),
        principles: section.principles
          .map((p) => ({
            principle: p,
            indicators: p.indicators.filter(matches(filter)),
          }))
          .filter((g) => g.indicators.length > 0),
      }
    })
  }, [framework, filter])

  if (isLoading) {
    return (
      <div className="sfp">
        <p className="sfp-loading">Loading BRSR form…</p>
      </div>
    )
  }

  if (error || !submission || !framework) {
    return (
      <div className="sfp">
        <div className="sfp-alert" role="alert">
          {error ?? 'Submission not found.'}
        </div>
        <button className="sfp-ghost" type="button" onClick={onClose}>
          Back to dashboard
        </button>
      </div>
    )
  }

  const total = countQuestions(framework)
  const answered = Object.keys(form.values).length
  /** True while any per-question answer save is still in flight. */
  const anySavePending = Object.values(form.saveState).some((s) => s === 'saving')

  return (
    <div className="sfp">
      <header className="sfp-head">
        <div>
          <h2 className="sfp-title">{framework.name}</h2>
          <p className="sfp-sub">
            {framework.name} v{framework.version} · {submission.status} ·{' '}
            {answered} of {total} answered
          </p>
        </div>
        <button className="sfp-ghost" type="button" onClick={onClose}>
          Close
        </button>
      </header>

      {readOnly ? (
        <div className="sfp-banner" role="note">
          This submission is {submission.status.replace(/_/g, ' ').toLowerCase()}.
          Answers are locked while it is out for review or approval, so the
          controls below are read-only.
        </div>
      ) : (
        <div className="sfp-banner sfp-banner--edit" role="note">
          Answers save one question at a time. Only the question you press Save
          on is sent — other edits stay on screen unsaved.
        </div>
      )}

      {!readOnly && (
        <div className="sfp-submit-bar">
          <button
            className="sfp-submit"
            type="button"
            disabled={submitOutcome.isSubmitting || anySavePending}
            onClick={onSubmit}
          >
            {submitOutcome.isSubmitting
              ? 'Submitting…'
              : submission?.status === 'CORRECTION_REQUIRED'
                ? 'Resubmit for Review'
                : 'Submit for Review'}
          </button>
          {anySavePending && (
            <span className="sfp-submit-hint">
              Waiting for an answer to finish saving…
            </span>
          )}
        </div>
      )}

      {submitOutcome.succeeded && (
        <p className="sfp-submit-ok" role="status">
          {submitOutcome.message}
        </p>
      )}

      {submitOutcome.error && (
        <p className="sfp-submit-err" role="alert">
          {submitOutcome.error}
        </p>
      )}

      {submitOutcome.missing.length > 0 && (
        <div className="sfp-missing" role="alert">
          <p className="sfp-missing-head">
            {submitOutcome.message}{' '}
            <strong>
              {submitOutcome.missing.length} mandatory question
              {submitOutcome.missing.length === 1 ? '' : 's'} still unanswered.
            </strong>
          </p>
          <ul className="sfp-missing-list">
            {submitOutcome.missing.map((m) => (
              <li key={m.question_id} className="sfp-missing-item">
                {/* One button per row, so the click never relies on bubbling
                    from the nested code/text spans. */}
                <button
                  className="sfp-missing-link"
                  type="button"
                  title={`Go to question ${m.code}`}
                  aria-label={`Go to question ${m.code}: ${m.question}`}
                  onClick={() => focusQuestion(m.question_id)}
                >
                  <span className="sfp-missing-code">{m.code}</span>
                  <span className="sfp-missing-text">{m.question}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="sfp-filters" role="group" aria-label="Filter by classification">
        {(['ALL', 'ESSENTIAL', 'LEADERSHIP'] as const).map((f) => (
          <button
            key={f}
            type="button"
            className={f === filter ? 'sfp-chip sfp-chip--on' : 'sfp-chip'}
            onClick={() => setFilter(f)}
          >
            {f === 'ALL' ? 'All' : f === 'ESSENTIAL' ? 'Essential' : 'Leadership'}
          </button>
        ))}
      </div>

      {sections.map(({ section, loose, principles }) => {
        const { loose: allLoose, nested: allNested } = partitionIndicators(section)
        const sectionQuestions =
          [...allLoose, ...allNested].reduce((n, i) => n + i.questions.length, 0)
        const shared = {
          form,
          readOnly,
          onEdit,
          onSave: saveQuestion,
          onUploadEvidence,
        }
        return (
          <section className="sfp-section" key={section.id}>
            <header className="sfp-section-head">
              <h3 className="sfp-section-title">
                {section.code} · {section.title}
              </h3>
              <span className="sfp-count">{sectionQuestions} questions</span>
            </header>

            {loose.map((indicator) => (
              <IndicatorBlock key={indicator.id} indicator={indicator} {...shared} />
            ))}

            {principles.map(({ principle, indicators }) => (
              <div className="sfp-principle" key={principle.id}>
                <h4 className="sfp-principle-title">
                  Principle {principle.principle_number} · {principle.title}
                </h4>
                {indicators.map((indicator) => (
                  <IndicatorBlock
                    key={indicator.id}
                    indicator={indicator}
                    {...shared}
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

/** Does this indicator pass the Essential/Leadership filter? */
function matches(filter: Filter) {
  return (i: BrsrIndicator) => filter === 'ALL' || i.indicator_type === filter
}

/** Remove one key without mutating the source object. */
function omit<T>(record: Record<string, T>, key: string): Record<string, T> {
  const { [key]: _dropped, ...rest } = record
  return rest
}

/** Human-readable byte size, e.g. 1536 -> "1.5 KB". */
function formatBytes(bytes: number | null): string {
  if (bytes === null) return 'Size unknown'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Group evidence under the question its answer belongs to.
 *
 * Evidence carries a submission_value_id, not a question_id, so the answer's
 * question is resolved through the saved values. Files attached at submission
 * level (no submission_value_id) are intentionally not surfaced - there is no
 * submission-level upload UI in this step.
 */
function groupEvidence(
  evidence: Evidence[],
  values: SubmissionValue[],
): Record<string, Evidence[]> {
  const questionIdByValue = new Map<string, string>()
  for (const v of values) questionIdByValue.set(v.id, v.question_id)

  const grouped: Record<string, Evidence[]> = {}
  for (const e of evidence) {
    if (!e.submission_value_id) continue
    const questionId = questionIdByValue.get(e.submission_value_id)
    if (!questionId) continue
    ;(grouped[questionId] ??= []).push(e)
  }
  return grouped
}

/** Turn an upload/API failure into a readable line. */
function describeUpload(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 400) return err.message
    if (err.status === 401) return 'Your session has expired. Please sign in again.'
    if (err.status === 403) return 'You do not have permission to add evidence.'
    if (err.status === 404) return 'That submission no longer exists.'
    return err.message
  }
  return 'Upload failed. Please try again.'
}

type Parsed =
  | { value_text: string | null; value_numeric: number | null; value_json: null }
  | { value_text: null; value_numeric: number | null; value_json: null }
  | { value_text: null; value_numeric: null; value_json: Record<string, unknown> }
  | { error: string }

/**
 * Convert the control's raw string into the three value fields.
 *
 * Only the field matching the question's response_type is populated; the other
 * two become explicit nulls. Validation happens here so an invalid NUMBER or a
 * TABLE payload that is not a JSON object never reaches the network.
 *
 * NOTE: the API does not validate response_type at all, so this mapping is a
 * client-side convention established by the verified contract.
 */
function toPayload(question: BrsrQuestion, raw: string): Parsed {
  const trimmed = raw.trim()

  switch (question.response_type) {
    case 'NUMBER': {
      if (trimmed === '') {
        return { value_text: null, value_numeric: null, value_json: null }
      }
      const n = Number(trimmed)
      if (!Number.isFinite(n)) {
        return { error: 'Enter a valid number, or leave the field empty.' }
      }
      return { value_text: null, value_numeric: n, value_json: null }
    }

    case 'TABLE': {
      if (trimmed === '') {
        return { value_text: null, value_numeric: null, value_json: null }
      }
      let parsed: unknown
      try {
        parsed = JSON.parse(trimmed)
      } catch {
        return { error: 'This is not valid JSON. Fix the syntax before saving.' }
      }
      if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
        return {
          error:
            'The answer must be a JSON object such as {"columns": [], "rows": []}. ' +
            'Arrays and plain values are rejected by the API.',
        }
      }
      return {
        value_text: null,
        value_numeric: null,
        value_json: parsed as Record<string, unknown>,
      }
    }

    default:
      return {
        value_text: trimmed === '' ? null : trimmed,
        value_numeric: null,
        value_json: null,
      }
  }
}

function describeSave(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 400) return err.message
    if (err.status === 403) return 'You do not have permission to edit this submission.'
    if (err.status === 422 && err.details) {
      const first = err.details[0]
      if (first && typeof first === 'object' && 'msg' in first) {
        return `The API rejected this answer: ${String((first as { msg: unknown }).msg)}`
      }
    }
    return err.message
  }
  return 'Could not save this answer. Please try again.'
}

function describe(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    if (err.status === 403) return 'You do not have access to this submission.'
    if (err.status === 404) return 'That submission no longer exists.'
    return err.message
  }
  return fallback
}

function IndicatorBlock({
  indicator,
  form,
  readOnly,
  onEdit,
  onSave,
  onUploadEvidence,
}: {
  indicator: BrsrIndicator
  form: FormState
  readOnly: boolean
  onEdit: (id: string, next: string) => void
  onSave: (q: BrsrQuestion) => void
  onUploadEvidence: (q: BrsrQuestion, file: File, description: string) => void
}) {
  const essential = indicator.indicator_type === 'ESSENTIAL'
  return (
    <article className="sfp-indicator">
      <header className="sfp-indicator-head">
        <h5 className="sfp-indicator-title">{indicator.title}</h5>
        <span className={essential ? 'sfp-tag sfp-tag--ess' : 'sfp-tag sfp-tag--lead'}>
          {essential ? 'Essential' : 'Leadership'}
        </span>
      </header>
      <p className="sfp-indicator-code">{indicator.code}</p>

      {indicator.questions.map((question) => (
        <QuestionRow
          key={question.id}
          question={question}
          form={form}
          readOnly={readOnly}
          onEdit={onEdit}
          onSave={onSave}
          onUploadEvidence={onUploadEvidence}
        />
      ))}
    </article>
  )
}

function QuestionRow({
  question,
  form,
  readOnly,
  onEdit,
  onSave,
  onUploadEvidence,
}: {
  question: BrsrQuestion
  form: FormState
  readOnly: boolean
  onEdit: (id: string, next: string) => void
  onSave: (q: BrsrQuestion) => void
  onUploadEvidence: (q: BrsrQuestion, file: File, description: string) => void
}) {
  const saved = form.values[question.id]
  const state = form.saveState[question.id] ?? 'idle'
  const error = form.message[question.id] ?? ''
  const answered = Boolean(saved)

  // The row is the stable scroll anchor and exists for every response type;
  // tabIndex lets focusQuestion() move focus here even when the control is a
  // plain div (BOOLEAN).
  return (
    <div className="sfp-question" id={`q-${question.id}`} tabIndex={-1}>
      <div className="sfp-q-head">
        <label className="sfp-q-label" htmlFor={`qc-${question.id}`}>
          <span className="sfp-q-code">{question.code}</span>
          <span className="sfp-q-text">{question.question_text}</span>
          {question.unit_of_measurement && (
            <span className="sfp-q-unit">({question.unit_of_measurement})</span>
          )}
          {question.is_mandatory && <span className="sfp-req">required</span>}
          {answered && <span className="sfp-answered">Answered</span>}
        </label>
      </div>

      {question.guidance && <p className="sfp-q-guidance">{question.guidance}</p>}

      <ResponseControl
        question={question}
        value={form.drafts[question.id] ?? serverText(question, saved)}
        readOnly={readOnly}
        onChange={(next) => onEdit(question.id, next)}
      />

      {error && (
        <p className="sfp-q-error" role="alert">
          {error}
        </p>
      )}

      {state === 'saved' && !error && (
        <p className="sfp-q-ok" role="status">
          Saved
        </p>
      )}

      {!readOnly && (
        <div className="sfp-q-actions">
          <button
            className="sfp-save"
            type="button"
            disabled={state === 'saving'}
            onClick={() => onSave(question)}
          >
            {state === 'saving' ? 'Saving…' : 'Save answer'}
          </button>
        </div>
      )}

      <EvidencePanel
        question={question}
        savedValueId={saved?.id}
        items={form.evidence[question.id] ?? []}
        state={form.uploadState[question.id] ?? 'idle'}
        message={form.uploadMessage[question.id] ?? ''}
        readOnly={readOnly}
        onUpload={onUploadEvidence}
      />
    </div>
  )
}

/**
 * Compact evidence list plus, for editable submissions whose answer has been
 * saved, an upload control.
 *
 * The upload control is intentionally hidden until a SubmissionValue exists:
 * the API's `submission_value_id` field takes an answer id, never a question
 * id, so there is nothing valid to send before the answer is saved.
 */
function EvidencePanel({
  question,
  savedValueId,
  items,
  state,
  message,
  readOnly,
  onUpload,
}: {
  question: BrsrQuestion
  savedValueId: string | undefined
  items: Evidence[]
  state: SaveState
  message: string
  readOnly: boolean
  onUpload: (q: BrsrQuestion, file: File, description: string) => void
}) {
  const [file, setFile] = useState<File | null>(null)
  const [description, setDescription] = useState('')
  const inputId = `ev-${question.id}`
  const busy = state === 'saving'
  const canUpload = !readOnly && Boolean(savedValueId) && Boolean(file) && !busy

  function submit() {
    if (!file || !canUpload) return
    onUpload(question, file, description)
    // Clear the picker so the same file can be re-selected if needed.
    setFile(null)
    setDescription('')
  }

  if (items.length === 0 && readOnly) return null

  return (
    <div className="sfp-ev">
      {items.length > 0 && (
        <ul className="sfp-ev-list">
          {items.map((e) => (
            <li className="sfp-ev-item" key={e.id}>
              <div className="sfp-ev-line">
                <span className="sfp-ev-name">{e.file_name}</span>
                <span className="sfp-ev-meta">
                  {formatBytes(e.file_size_bytes)}
                  {e.content_type ? ` · ${e.content_type}` : ''}
                </span>
              </div>
              {e.description && <p className="sfp-ev-desc">{e.description}</p>}
              {e.created_at && (
                <p className="sfp-ev-date">
                  Uploaded {formatDate(e.created_at)}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {!readOnly && savedValueId && (
        <div className="sfp-ev-upload">
          <label className="sfp-ev-label" htmlFor={inputId}>
            Evidence
          </label>
          <div className="sfp-ev-controls">
            <input
              className="sfp-ev-file"
              id={inputId}
              type="file"
              disabled={busy}
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <input
              className="sfp-ev-desc-input"
              type="text"
              placeholder="Description (optional)"
              value={description}
              disabled={busy}
              onChange={(e) => setDescription(e.target.value)}
            />
            <button
              className="sfp-ev-btn"
              type="button"
              disabled={!canUpload}
              onClick={submit}
            >
              {busy ? 'Uploading…' : 'Upload Evidence'}
            </button>
          </div>
          {state === 'saved' && !message && (
            <p className="sfp-q-ok" role="status">
              Evidence uploaded
            </p>
          )}
          {message && (
            <p className="sfp-q-error" role="alert">
              {message}
            </p>
          )}
        </div>
      )}

      {!readOnly && !savedValueId && (
        <p className="sfp-ev-note">Save the answer first to attach evidence.</p>
      )}
    </div>
  )
}

/** Render an evidence upload timestamp. */
function formatDate(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

/**
 * Renders the control that matches the question's actual response_type.
 * Read-only controls are shown when the submission is not editable; the
 * TABLE placeholder is used in that case, and a JSON-object editor otherwise.
 */
function ResponseControl({
  question,
  value,
  readOnly,
  onChange,
}: {
  question: BrsrQuestion
  value: string
  readOnly: boolean
  onChange: (next: string) => void
}) {
  // Control ids keep the UUID scheme but use a distinct prefix so they never
  // collide with the row's q-<id> scroll anchor (duplicate ids are invalid
  // HTML and would make getElementById return the wrong node).
  const id = `qc-${question.id}`
  const off = readOnly ? { disabled: true } : {}
  const common = {
    id,
    className: 'sfp-input',
    value,
    onChange: (e: { target: { value: string } }) => onChange(e.target.value),
  }

  switch (question.response_type) {
    case 'NUMBER':
      return <input {...common} {...off} type="number" step="any" placeholder="Not answered" />

    case 'BOOLEAN':
      // Yes/No are stored as value_text. The API defines no boolean options,
      // but a yes/no disclosure question is unambiguous in SEBI's wording.
      return (
        <div className="sfp-bool" role="group" aria-label="Yes or no">
          {['Yes', 'No'].map((opt) => (
            <button
              key={opt}
              type="button"
              className={value === opt ? 'sfp-bool-btn sfp-bool-btn--on' : 'sfp-bool-btn'}
              disabled={readOnly}
              aria-pressed={value === opt}
              onClick={() => onChange(value === opt ? '' : opt)}
            >
              {opt}
            </button>
          ))}
          {value && value !== 'Yes' && value !== 'No' && (
            <span className="sfp-bool-other">{value}</span>
          )}
        </div>
      )

    case 'TEXT':
      return <textarea {...common} {...off} className="sfp-input sfp-textarea" rows={2} placeholder="Not answered" />

    case 'SELECT':
      // Unreachable against today's data (0 SELECT questions) and the API
      // carries no option metadata, so no options are invented here.
      return (
        <>
          <input {...common} {...off} type="text" placeholder="Not answered" />
          <p className="sfp-hint">Options not provided by the API — enter the value as free text.</p>
        </>
      )

    case 'TABLE':
      if (readOnly) {
        // Keep the Step 2A placeholder in read-only mode; no columns are invented.
        return (
          <div className="sfp-table-placeholder" id={id}>
            <span className="sfp-table-note">
              Table response — the required row and column structure is defined by
              the question text above and is not supplied as metadata by the API.
            </span>
            {value && <span className="sfp-table-value">Stored answer: {value}</span>}
          </div>
        )
      }
      return (
        <>
          <textarea
            {...common}
            className="sfp-input sfp-textarea sfp-json"
            rows={5}
            spellCheck={false}
            placeholder={'{\n  "columns": [],\n  "rows": []\n}'}
          />
          <p className="sfp-hint">
            Must be a JSON object. The API rejects arrays and scalars; column
            definitions come from the question text.
          </p>
        </>
      )

    default:
      return (
        <input
          {...common}
          {...off}
          type="text"
          placeholder={`Unsupported type: ${String(question.response_type)}`}
        />
      )
  }
}