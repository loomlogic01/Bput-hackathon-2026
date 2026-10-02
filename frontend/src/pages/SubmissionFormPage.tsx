import { useEffect, useMemo, useState } from 'react'

import type {
  BrsrFrameworkDetail,
  BrsrIndicator,
  BrsrIndicatorType,
  BrsrQuestion,
  Submission,
  SubmissionValue,
} from '../api/client'
import {
  ApiError,
  getFramework,
  getSubmission,
  listSubmissionValues,
  partitionIndicators,
} from '../api/client'
import { useAuth } from '../auth/AuthContext'
import './SubmissionFormPage.css'

interface Props {
  submissionId: string
  onClose: () => void
}

type Loaded = {
  submission: Submission
  framework: BrsrFrameworkDetail
  /** Answers indexed by question_id; [] for a fresh DRAFT submission. */
  values: Map<string, SubmissionValue>
}

type Filter = 'ALL' | BrsrIndicatorType

/** Questions answered so far, for the header progress line. */
function answeredCount(values: Map<string, SubmissionValue>): number {
  return values.size
}

/** Total questions in a framework, following the verified partition rule. */
function countQuestions(framework: BrsrFrameworkDetail): number {
  return framework.sections.reduce((total, section) => {
    const { loose, nested } = partitionIndicators(section)
    const all = [...loose, ...nested]
    return total + all.reduce((n, i) => n + i.questions.length, 0)
  }, 0)
}

export default function SubmissionFormPage({
  submissionId,
  onClose,
}: Props) {
  const { token } = useAuth()

  const [data, setData] = useState<Loaded | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<Filter>('ALL')

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
      let submission: Submission
      try {
        submission = await getSubmission(submissionId, authToken)
      } catch (err) {
        if (!cancelled) {
          setError(describe(err, 'Could not load this submission.'))
          setIsLoading(false)
        }
        return
      }

      try {
        const [framework, values] = await Promise.all([
          getFramework(submission.framework_id, authToken),
          listSubmissionValues(submissionId, authToken),
        ])
        if (cancelled) return
        setData({
          submission,
          framework,
          values: new Map(values.map((v) => [v.question_id, v])),
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

  const sections = useMemo(() => {
    if (!data) return []
    return data.framework.sections.map((section) => {
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
  }, [data, filter])

  if (isLoading) {
    return (
      <div className="sfp">
        <p className="sfp-loading">Loading BRSR form…</p>
      </div>
    )
  }

  if (error || !data) {
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

  const total = countQuestions(data.framework)
  const answered = answeredCount(data.values)

  return (
    <div className="sfp">
      <header className="sfp-head">
        <div>
          <h2 className="sfp-title">{data.framework.name}</h2>
          <p className="sfp-sub">
            {data.framework.name} v{data.framework.version} ·{' '}
            {data.submission.status} · {answered} of {total} answered
          </p>
        </div>
        <button className="sfp-ghost" type="button" onClick={onClose}>
          Close
        </button>
      </header>

      <div className="sfp-banner" role="note">
        Read-only preview. Answer capture arrives in the next milestone — every
        control below is disabled.
      </div>

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
        return (
          <section className="sfp-section" key={section.id}>
            <header className="sfp-section-head">
              <h3 className="sfp-section-title">
                {section.code} · {section.title}
              </h3>
              <span className="sfp-count">{sectionQuestions} questions</span>
            </header>

            {loose.map((indicator) => (
              <IndicatorBlock
                key={indicator.id}
                indicator={indicator}
                values={data.values}
              />
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
                    values={data.values}
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
  values,
}: {
  indicator: BrsrIndicator
  values: Map<string, SubmissionValue>
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
        <QuestionRow key={question.id} question={question} value={values.get(question.id)} />
      ))}
    </article>
  )
}

function QuestionRow({
  question,
  value,
}: {
  question: BrsrQuestion
  value: SubmissionValue | undefined
}) {
  return (
    <div className="sfp-question">
      <label className="sfp-q-label" htmlFor={`q-${question.id}`}>
        <span className="sfp-q-code">{question.code}</span>
        <span className="sfp-q-text">{question.question_text}</span>
        {question.unit_of_measurement && (
          <span className="sfp-q-unit">({question.unit_of_measurement})</span>
        )}
        {question.is_mandatory && <span className="sfp-req">required</span>}
      </label>

      {question.guidance && <p className="sfp-q-guidance">{question.guidance}</p>}

      <ResponseControl question={question} value={value} />
    </div>
  )
}

/**
 * Renders the control that matches the question's actual response_type.
 * Everything is disabled in Step 2A - no handler is attached.
 */
function ResponseControl({
  question,
  value,
}: {
  question: BrsrQuestion
  value: SubmissionValue | undefined
}) {
  const id = `q-${question.id}`
  const display = value
    ? (value.value_text ?? (value.value_numeric !== null ? String(value.value_numeric) : ''))
    : ''

  switch (question.response_type) {
    case 'NUMBER':
      return (
        <input
          className="sfp-input"
          id={id}
          type="number"
          disabled
          readOnly
          value={display}
          placeholder="Not answered"
        />
      )

    case 'BOOLEAN':
      // The API exposes no boolean options; render the stored value as text
      // rather than assuming a Yes/No control the contract does not define.
      return (
        <input
          className="sfp-input"
          id={id}
          type="text"
          disabled
          readOnly
          value={display}
          placeholder="Not answered"
        />
      )

    case 'TEXT':
      return (
        <textarea
          className="sfp-input sfp-textarea"
          id={id}
          rows={2}
          disabled
          readOnly
          value={display}
          placeholder="Not answered"
        />
      )

    case 'SELECT':
      // Unreachable against today's data (0 SELECT questions) and the API
      // carries no option metadata, so no options are invented here.
      return (
        <input
          className="sfp-input"
          id={id}
          type="text"
          disabled
          readOnly
          value={display}
          placeholder="Choice list not provided by the API"
        />
      )

    case 'TABLE':
      // 58 of the 140 Full BRSR questions are TABLE. The API defines no
      // columns, so Step 2A shows a placeholder rather than a fabricated grid.
      return (
        <div className="sfp-table-placeholder" id={id}>
          <span className="sfp-table-note">
            Table response — the required row and column structure is defined by
            the question text above and is not supplied as metadata by the API.
          </span>
          {value && (
            <span className="sfp-table-value">
              Stored answer: {value.value_text ?? JSON.stringify(value.value_json)}
            </span>
          )}
        </div>
      )

    default:
      return (
        <input
          className="sfp-input"
          id={id}
          type="text"
          disabled
          readOnly
          value={display}
          placeholder={`Unsupported type: ${String(question.response_type)}`}
        />
      )
  }
}