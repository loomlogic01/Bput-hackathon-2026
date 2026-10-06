/**
 * Minimal API client for the ESG/BRSR backend.
 *
 * Uses the browser's native fetch - no HTTP library (no axios, no ky).
 *
 * Authentication is deliberately NOT handled here yet: this module performs
 * no login and stores no token. A caller may pass a bearer token per request
 * via `options.token`, because most endpoints require one.
 */

/** Base URL of the backend, including the /api/v1 prefix. */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1'

/** An HTTP error response from the backend. */
export class ApiError extends Error {
  readonly status: number
  /**
   * FastAPI returns `detail` as a string for 401/403/404 and as an *array* of
   * validation objects for 422. When it is an array it is surfaced here so a
   * caller can explain what failed; `message` keeps the status-line fallback.
   */
  readonly details?: unknown[]
  /**
   * Some endpoints (e.g. submit's mandatory-question check) return a *structured*
   * object in `detail` rather than a string. Preserved here so the caller can
   * read its fields instead of only seeing "400 Bad Request".
   */
  readonly objectDetail?: Record<string, unknown>

  constructor(
    status: number,
    message: string,
    details?: unknown[],
    objectDetail?: Record<string, unknown>,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.details = details
    this.objectDetail = objectDetail
  }
}

/** One unanswered mandatory question returned by POST /submissions/{id}/submit. */
export interface MissingQuestion {
  question_id: string
  code: string
  question: string
}

export interface RequestOptions extends Omit<RequestInit, 'body'> {
  /** Serialised as JSON when provided. */
  body?: unknown
  /** Optional bearer token for this request only. Not stored. */
  token?: string
}

/** Perform a request against the backend and return the parsed JSON body. */
export async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { body, token, headers, ...rest } = options

  // FormData must be passed through untouched and must NOT carry a
  // Content-Type header - the browser sets it with the multipart boundary.
  const isFormData = typeof FormData !== 'undefined' && body instanceof FormData
  const hasJsonBody = body !== undefined && !isFormData

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      Accept: 'application/json',
      ...(hasJsonBody ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: isFormData ? body : JSON.stringify(body) } : {}),
  })

  if (!response.ok) {
    // FastAPI reports errors as { "detail": ... }; fall back to the status line.
    let detail = `${response.status} ${response.statusText}`
    let details: unknown[] | undefined
    let objectDetail: Record<string, unknown> | undefined
    try {
      const payload = await response.json()
      if (payload && typeof payload.detail === 'string') {
        detail = payload.detail
      } else if (payload && Array.isArray(payload.detail)) {
        // 422 validation errors - keep the array for the caller to render.
        details = payload.detail
      } else if (
        payload &&
        payload.detail &&
        typeof payload.detail === 'object'
      ) {
        // Structured detail (e.g. submit's missing_questions) - keep the object.
        objectDetail = payload.detail as Record<string, unknown>
        detail =
          typeof payload.detail.message === 'string'
            ? payload.detail.message
            : detail
      }
    } catch {
      // Non-JSON error body - keep the status line.
    }
    throw new ApiError(response.status, detail, details, objectDetail)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

// ── BRSR framework endpoints ──

export interface BrsrFramework {
  id: string
  name: string
  version: string
  description: string | null
  is_active: boolean
}

/** GET /brsr/ - all active BRSR frameworks. */
export function listFrameworks(token?: string): Promise<BrsrFramework[]> {
  return request<BrsrFramework[]>('/brsr/', { token })
}

// ── BRSR hierarchy (GET /brsr/{id}) ──

/**
 * The response types the backend enum defines. The API serialises
 * `response_type` as a plain string, so an unrecognised value must still
 * render rather than crash - the renderer falls back to a read-only box.
 */
export type BrsrResponseType =
  | 'NUMBER'
  | 'TEXT'
  | 'BOOLEAN'
  | 'SELECT'
  | 'TABLE'

/** SEBI distinguishes mandatory from voluntary disclosures per indicator. */
export type BrsrIndicatorType = 'ESSENTIAL' | 'LEADERSHIP'

export interface BrsrQuestion {
  id: string
  code: string
  question_text: string
  guidance: string | null
  response_type: BrsrResponseType
  unit_of_measurement: string | null
  is_mandatory: boolean
  order_index: number
}

export interface BrsrIndicator {
  id: string
  code: string
  title: string
  indicator_type: BrsrIndicatorType
  order_index: number
  section_id: string
  /** Null for indicators attached directly to a section (Sections A and B). */
  principle_id: string | null
  questions: BrsrQuestion[]
}

export interface BrsrPrinciple {
  id: string
  principle_number: number
  code: string
  title: string
  description: string | null
  order_index: number
  indicators: BrsrIndicator[]
}

export interface BrsrSection {
  id: string
  code: string
  title: string
  description: string | null
  order_index: number
  principles: BrsrPrinciple[]
  /**
   * Every indicator in this section - INCLUDING the ones nested under
   * `principles`. Do not render this array directly; use
   * partitionIndicators() below or principle-level questions appear twice.
   */
  indicators: BrsrIndicator[]
}

export interface BrsrFrameworkDetail extends BrsrFramework {
  sections: BrsrSection[]
}

/**
 * Split a section's indicators into the two groups the API returns.
 *
 * An indicator carries a required section_id and an OPTIONAL principle_id,
 * and both relationships are serialised, so `section.indicators` is a
 * superset of `principle.indicators`. Verified against the live API:
 * Full BRSR (SEBI BRSR v2021) has 27 indicators / 140 questions, of which 18
 * indicators appear in both arrays; BRSR Core has 2 / 4 with 1 duplicated.
 * Partitioning this way yields exactly 27/140 and 2/4 with no overlap.
 */
export function partitionIndicators(section: BrsrSection): {
  loose: BrsrIndicator[]
  nested: BrsrIndicator[]
} {
  return {
    loose: section.indicators.filter((i) => i.principle_id === null),
    nested: section.principles.flatMap((p) => p.indicators),
  }
}

/** GET /brsr/{framework_id} - full section/principle/indicator/question tree. */
export function getFramework(
  frameworkId: string,
  token?: string,
): Promise<BrsrFrameworkDetail> {
  return request<BrsrFrameworkDetail>(`/brsr/${frameworkId}`, { token })
}

// ── Project & reporting period endpoints ──

export interface Project {
  id: string
  name: string
  code: string | null
  location: string | null
  business_unit_id: string
}

export interface ReportingPeriod {
  id: string
  fiscal_year: string
  start_date: string
  end_date: string
  boundary: string
  description: string | null
  organization_id: string
}

/** GET /projects/ - projects within the caller's scope. */
export function listProjects(token?: string): Promise<Project[]> {
  return request<Project[]>('/projects/', { token })
}

/** GET /projects/reporting-periods - periods within the caller's scope. */
export function listReportingPeriods(
  token?: string,
): Promise<ReportingPeriod[]> {
  return request<ReportingPeriod[]>('/projects/reporting-periods', { token })
}

// ── Submission endpoints ──

export interface Submission {
  id: string
  status: string
  comments: string | null
  project_id: string
  reporting_period_id: string
  framework_id: string
  created_by_id: string | null
  created_at: string | null
  updated_at: string | null
  /**
   * Display name of the linked reporting period (e.g. "FY 2025-26"), resolved
   * server-side from this submission. Lets a read-only Approver show the period
   * without access to /projects/reporting-periods. Null if unresolved.
   */
  reporting_period_label: string | null
}

/** GET /submissions/ - submissions within the caller's scope. */
export function listSubmissions(token?: string): Promise<Submission[]> {
  return request<Submission[]>('/submissions/', { token })
}

/** Body accepted by POST /submissions/ (SubmissionCreateRequest). */
export interface CreateSubmissionInput {
  project_id: string
  reporting_period_id: string
  framework_id: string
  /** Optional. These are the submission's own notes, not a workflow comment. */
  comments?: string | null
}

/**
 * POST /submissions/ - create a DRAFT submission.
 *
 * Requires the `submission:create` permission and the project to be in the
 * caller's scope, otherwise the API answers 403.
 */
export function createSubmission(
  token: string,
  input: CreateSubmissionInput,
): Promise<Submission> {
  return request<Submission>('/submissions/', {
    method: 'POST',
    body: input,
    token,
  })
}

/** GET /submissions/{id} - a single submission within the caller's scope. */
export function getSubmission(
  submissionId: string,
  token?: string,
): Promise<Submission> {
  return request<Submission>(`/submissions/${submissionId}`, { token })
}

/**
 * A saved answer for one BRSR question. At most one row exists per
 * (submission_id, question_id) - the POST endpoint upserts.
 */
export interface SubmissionValue {
  id: string
  submission_id: string
  question_id: string
  value_text: string | null
  value_numeric: number | null
  /** Structured payloads (e.g. TABLE answers) land here. */
  value_json: Record<string, unknown> | null
  data_source: string | null
  calculation_method: string | null
  source_department: string | null
  created_at: string | null
  updated_at: string | null
}

/**
 * GET /submissions/{id}/values - every saved answer for a submission.
 *
 * Returned as a flat list with no question embedded, so callers must index
 * by `question_id`. A submission with no answers returns [].
 */
export function listSubmissionValues(
  submissionId: string,
  token?: string,
): Promise<SubmissionValue[]> {
  return request<SubmissionValue[]>(`/submissions/${submissionId}/values`, {
    token,
  })
}

/**
 * Body accepted by POST /submissions/{id}/values.
 *
 * IMPORTANT: the endpoint performs a FULL REPLACEMENT upsert - it matches on
 * (submission_id, question_id) and then overwrites all six value/metadata
 * columns with whatever this payload carries. Omitting a field therefore
 * clears it to NULL rather than leaving it untouched. Always send the whole
 * object, never a sparse patch.
 */
export interface SaveSubmissionValueInput {
  question_id: string
  value_text?: string | null
  value_numeric?: number | null
  /** Must be a JSON object; an array or scalar is rejected with 422. */
  value_json?: Record<string, unknown> | null
  data_source?: string | null
  calculation_method?: string | null
  source_department?: string | null
}

/**
 * POST /submissions/{id}/values - create or replace one answer.
 *
 * Returns 201 both when creating a new row and when updating an existing one
 * (same row id is reused). Only DRAFT and CORRECTION_REQUIRED submissions may
 * be written; anything else returns 400.
 */
export function saveSubmissionValue(
  submissionId: string,
  input: SaveSubmissionValueInput,
  token?: string,
): Promise<SubmissionValue> {
  return request<SubmissionValue>(`/submissions/${submissionId}/values`, {
    method: 'POST',
    body: input,
    token,
  })
}

// ── Workflow ──

/** An ApprovalWorkflow audit row returned by each transition endpoint. */
export interface SubmissionWorkflowResponse {
  id: string
  submission_id: string
  from_status: string
  to_status: string
  action_by_id: string | null
  comments: string | null
  created_at: string | null
  updated_at: string | null
}

/**
 * POST /submissions/{id}/submit - move DRAFT -> SUBMITTED.
 *
 * The endpoint takes a WorkflowActionRequest body, so `{}` is sent even when
 * no comment is supplied; omitting the body entirely returns 422.
 *
 * Returns 200 on success. When mandatory questions are still unanswered it
 * returns 400 whose `detail` is an object:
 *   { message, missing_questions: [{ question_id, code, question }] }
 * which `request()` surfaces as ApiError.objectDetail.
 */
export function submitSubmission(
  submissionId: string,
  token?: string,
): Promise<SubmissionWorkflowResponse> {
  return request<SubmissionWorkflowResponse>(
    `/submissions/${submissionId}/submit`,
    { method: 'POST', body: {}, token },
  )
}

/**
 * POST /submissions/{id}/resubmit - CORRECTION_REQUIRED -> RESUBMITTED.
 *
 * The endpoint takes a WorkflowActionRequest body, so `{}` is always sent;
 * omitting the body entirely returns 422. The backend performs NO
 * mandatory-question validation on this transition (unlike /submit).
 */
export function resubmitSubmission(
  submissionId: string,
  comments?: string | null,
  token?: string,
): Promise<SubmissionWorkflowResponse> {
  return request<SubmissionWorkflowResponse>(
    `/submissions/${submissionId}/resubmit`,
    { method: 'POST', body: { comments: comments ?? null }, token },
  )
}

/**
 * POST /submissions/{id}/review - SUBMITTED or RESUBMITTED -> UNDER_REVIEW.
 *
 * The body is always a JSON object because the endpoint takes a
 * WorkflowActionRequest; omitting it entirely returns 422.
 */
export function reviewSubmission(
  submissionId: string,
  comments?: string | null,
  token?: string,
): Promise<SubmissionWorkflowResponse> {
  return request<SubmissionWorkflowResponse>(
    `/submissions/${submissionId}/review`,
    { method: 'POST', body: { comments: comments ?? null }, token },
  )
}

/**
 * POST /submissions/{id}/request-correction - UNDER_REVIEW -> CORRECTION_REQUIRED.
 *
 * `comments` is mandatory and must be non-blank: omitting the key returns 422
 * (schema) while a whitespace-only value returns 400 (handler). Callers must
 * validate before sending.
 */
export function requestCorrection(
  submissionId: string,
  comments: string,
  token?: string,
): Promise<SubmissionWorkflowResponse> {
  return request<SubmissionWorkflowResponse>(
    `/submissions/${submissionId}/request-correction`,
    { method: 'POST', body: { comments }, token },
  )
}

/**
 * POST /submissions/{id}/approve - UNDER_REVIEW|RESUBMITTED -> APPROVED.
 *
 * Requires `submission:approve`. The request body is REQUIRED by the backend:
 * a bodiless POST returns 422, not 400. `comments` is optional, so an absent
 * comment is sent as an explicit null rather than by omitting the key.
 */
export function approveSubmission(
  submissionId: string,
  comments?: string,
  token?: string,
): Promise<SubmissionWorkflowResponse> {
  return request<SubmissionWorkflowResponse>(
    `/submissions/${submissionId}/approve`,
    { method: 'POST', body: { comments: comments ?? null }, token },
  )
}

/**
 * POST /submissions/{id}/lock - APPROVED -> LOCKED.
 *
 * Requires `submission:approve`. Like /approve the body is mandatory and
 * `comments` is optional, so it is always sent as an explicit null when absent.
 * LOCKED is terminal - the backend has no transition out of it.
 */
export function lockSubmission(
  submissionId: string,
  comments?: string,
  token?: string,
): Promise<SubmissionWorkflowResponse> {
  return request<SubmissionWorkflowResponse>(
    `/submissions/${submissionId}/lock`,
    { method: 'POST', body: { comments: comments ?? null }, token },
  )
}

/** GET /submissions/{id}/workflow - audit trail, oldest first. */
export function listWorkflow(
  submissionId: string,
  token?: string,
): Promise<SubmissionWorkflowResponse[]> {
  return request<SubmissionWorkflowResponse[]>(
    `/submissions/${submissionId}/workflow`,
    { token },
  )
}

// ── Evidence ──

/**
 * An evidence attachment. Note the API deliberately does not return
 * `storage_path` - the server-side location is never exposed to a client.
 */
export interface Evidence {
  id: string
  file_name: string
  content_type: string | null
  file_size_bytes: number | null
  description: string | null
  submission_id: string
  /** Set when the file is attached to one specific saved answer. */
  submission_value_id: string | null
  uploaded_by_id: string | null
  created_at: string | null
  updated_at: string | null
}

/** GET /submissions/{id}/evidence - requires submission:read. */
export function listEvidence(
  submissionId: string,
  token?: string,
): Promise<Evidence[]> {
  return request<Evidence[]>(`/submissions/${submissionId}/evidence`, { token })
}

/**
 * POST /submissions/{id}/evidence - multipart upload.
 *
 * Only DRAFT and CORRECTION_REQUIRED submissions accept uploads; other
 * statuses return 400. An empty file or one over MAX_UPLOAD_SIZE also 400s.
 *
 * `submissionValueId` must be the id of a SAVED SubmissionValue (never a
 * question id); omit it to attach the file at submission level.
 */
export function uploadEvidence(
  submissionId: string,
  file: File,
  options: {
    description?: string
    submissionValueId?: string
  } = {},
  token?: string,
): Promise<Evidence> {
  const data = new FormData()
  data.append('file', file)
  if (options.description) data.append('description', options.description)
  if (options.submissionValueId) {
    data.append('submission_value_id', options.submissionValueId)
  }
  return request<Evidence>(`/submissions/${submissionId}/evidence`, {
    method: 'POST',
    body: data,
    token,
  })
}

// ── Authentication endpoints ──
// This module performs no token storage. The caller (AuthContext) owns the
// token and passes it per request.

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
}

export interface CurrentUser {
  id: string
  email: string
  full_name: string
  is_active: boolean
  organization_id: string | null
  entity_id: string | null
  business_unit_id: string | null
  project_id: string | null
}

/** POST /auth/login - exchange credentials for a bearer token. */
export function login(credentials: LoginRequest): Promise<LoginResponse> {
  return request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: credentials,
  })
}

/** GET /auth/me - resolve the signed-in user from a bearer token. */
export function getCurrentUser(token: string): Promise<CurrentUser> {
  return request<CurrentUser>('/auth/me', { token })
}

// ── Consolidation endpoint ──

/** Types for the consolidation API response */
export interface ConsolidatedMetric {
  question_code: string;
  question: string;
  aggregated_value: number;
  unit_of_measurement: string;
  contributing_project_count: number;
  aggregation: string;
  aggregated_value_is_meaningful: boolean;
}

export interface ConsolidatedDerivedKPI {
  code: string;
  label: string;
  unit: string;
  calculation_method: string;
  source_question_codes: string[];
  value: number | null;
  contributing_project_count: number;
}

export interface ConsolidationTotals {
  projects_contributing: number;
  metrics_aggregated: number;
}

export interface ConsolidationResponse {
  reporting_period: any; // could be refined with a dedicated interface
  framework: any;
  projects: any[];
  metrics: ConsolidatedMetric[];
  derived_kpis: ConsolidatedDerivedKPI[];
  totals: ConsolidationTotals;
}

/** GET /reporting/consolidation?reporting_period_id=<id>&framework_id=<id> */
export function getConsolidation(
  reportingPeriodId: string,
  frameworkId: string,
  token?: string,
): Promise<ConsolidationResponse> {
  const path = `/reporting/consolidation?reporting_period_id=${reportingPeriodId}&framework_id=${frameworkId}`;
  return request<ConsolidationResponse>(path, { token });
}