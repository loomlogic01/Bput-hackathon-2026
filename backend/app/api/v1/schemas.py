"""
Pydantic request/response schemas for the BRSR API endpoints.
"""

import uuid
from datetime import date
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict


# ── Projects ──

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    code: Optional[str] = None
    location: Optional[str] = None
    business_unit_id: uuid.UUID


# ── Reporting Periods ──

class ReportingPeriodResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    fiscal_year: str
    start_date: date
    end_date: date
    boundary: str
    description: Optional[str] = None
    organization_id: uuid.UUID


# ── BRSR Framework (nested hierarchy) ──

class BRSRQuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    question_text: str
    guidance: Optional[str] = None
    response_type: str
    unit_of_measurement: Optional[str] = None
    is_mandatory: bool
    order_index: int


class BRSRIndicatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    title: str
    indicator_type: str
    order_index: int
    section_id: uuid.UUID
    principle_id: Optional[uuid.UUID] = None
    questions: List[BRSRQuestionResponse] = []


class BRSRPrincipleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    principle_number: int
    code: str
    title: str
    description: Optional[str] = None
    order_index: int
    indicators: List[BRSRIndicatorResponse] = []


class BRSRSectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    title: str
    description: Optional[str] = None
    order_index: int
    principles: List[BRSRPrincipleResponse] = []
    indicators: List[BRSRIndicatorResponse] = []


class BRSRFrameworkListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: str
    description: Optional[str] = None
    is_active: bool


class BRSRFrameworkDetailResponse(BRSRFrameworkListResponse):
    sections: List[BRSRSectionResponse] = []


# ── Submissions ──

class SubmissionCreateRequest(BaseModel):
    project_id: uuid.UUID
    reporting_period_id: uuid.UUID
    framework_id: uuid.UUID
    comments: Optional[str] = None


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    status: str
    comments: Optional[str] = None
    project_id: uuid.UUID
    reporting_period_id: uuid.UUID
    framework_id: uuid.UUID
    created_by_id: Optional[uuid.UUID] = None
    created_at: Any = None
    updated_at: Any = None
    # Display name of the linked reporting period (e.g. "FY 2025-26"). Resolved
    # from the submission the caller is ALREADY authorized to read, so it does
    # not widen access to /projects/reporting-periods.
    reporting_period_label: Optional[str] = None


# ── Reporting & consolidation ──

class ConsolidationPeriodSummary(BaseModel):
    id: uuid.UUID
    fiscal_year: str
    start_date: date
    end_date: date
    boundary: Optional[str] = None


class ConsolidationFrameworkSummary(BaseModel):
    id: uuid.UUID
    name: str
    version: str


class ConsolidationProject(BaseModel):
    """One contributing project with its full organisation chain."""
    organization_id: Optional[uuid.UUID] = None
    organization_name: Optional[str] = None
    organization_code: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    entity_name: Optional[str] = None
    entity_code: Optional[str] = None
    business_unit_id: Optional[uuid.UUID] = None
    business_unit_name: Optional[str] = None
    business_unit_code: Optional[str] = None
    project_id: uuid.UUID
    project_name: str
    project_code: Optional[str] = None
    # Which submission was chosen as canonical for this project.
    submission_id: uuid.UUID
    submission_status: str


class ConsolidationMetric(BaseModel):
    """One NUMBER question aggregated across the contributing projects.

    Only questions of type NUMBER are ever present. Two questions are never
    merged, even if their unit_of_measurement strings match.
    """
    question_id: uuid.UUID
    question_code: str
    question_text: str
    unit_of_measurement: Optional[str] = None
    is_mandatory: bool
    section_code: Optional[str] = None
    section_title: Optional[str] = None
    indicator_code: Optional[str] = None
    indicator_title: Optional[str] = None
    indicator_type: Optional[str] = None
    # None for Section A/B indicators, which sit outside the NGRBC principles.
    principle_code: Optional[str] = None
    principle_title: Optional[str] = None
    aggregated_value: float
    contributing_project_count: int
    contributing_project_ids: List[uuid.UUID] = []


class ConsolidationTotals(BaseModel):
    projects_contributing: int
    metrics_aggregated: int


class ConsolidationResponse(BaseModel):
    """Request-time aggregate of approved/locked submissions.

    An empty dataset is a valid 200 with empty ``projects``/``metrics`` lists,
    never an error.
    """
    reporting_period: ConsolidationPeriodSummary
    framework: ConsolidationFrameworkSummary
    projects: List[ConsolidationProject] = []
    metrics: List[ConsolidationMetric] = []
    totals: ConsolidationTotals


# ── Submission Values ──

class SubmissionValueCreateRequest(BaseModel):
    question_id: uuid.UUID
    value_text: Optional[str] = None
    value_numeric: Optional[float] = None
    value_json: Optional[dict] = None
    data_source: Optional[str] = None
    calculation_method: Optional[str] = None
    source_department: Optional[str] = None


class SubmissionValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    submission_id: uuid.UUID
    question_id: uuid.UUID
    value_text: Optional[str] = None
    value_numeric: Optional[float] = None
    value_json: Optional[dict] = None
    data_source: Optional[str] = None
    calculation_method: Optional[str] = None
    source_department: Optional[str] = None
    created_at: Any = None
    updated_at: Any = None


# ── Evidence ──

class EvidenceResponse(BaseModel):
    """An evidence attachment recorded against a submission.

    Deliberately omits ``storage_path``: it is a server-side relative location
    and is never returned to a client.
    """

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    file_name: str
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    description: Optional[str] = None
    submission_id: uuid.UUID
    submission_value_id: Optional[uuid.UUID] = None
    uploaded_by_id: Optional[uuid.UUID] = None
    created_at: Any = None
    updated_at: Any = None


# ── Submission Workflow ──

class WorkflowActionRequest(BaseModel):
    """Body for a workflow transition. The review comment is optional."""

    comments: Optional[str] = None


class RequestCorrectionRequest(BaseModel):
    """Body for request-correction. A reason is mandatory."""

    comments: str


class SubmissionWorkflowResponse(BaseModel):
    """An ApprovalWorkflow row recording one status transition."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    submission_id: uuid.UUID
    from_status: str
    to_status: str
    action_by_id: Optional[uuid.UUID] = None
    comments: Optional[str] = None
    created_at: Any = None
