"""
Submission and SubmissionValue CRUD endpoints.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.v1.schemas import (
    RequestCorrectionRequest,
    SubmissionCreateRequest,
    SubmissionResponse,
    SubmissionValueCreateRequest,
    SubmissionValueResponse,
    SubmissionWorkflowResponse,
    WorkflowActionRequest,
)
from backend.app.db.database import get_db
from backend.app.db.models.brsr import BRSRFramework, BRSRQuestion
from backend.app.db.models.organization import Project
from backend.app.db.models.reporting import ReportingPeriod
from backend.app.db.models.submission import (
    ApprovalWorkflow,
    Submission,
    SubmissionStatus,
    SubmissionValue,
)
from backend.app.db.models.user import User

router = APIRouter()

EDITABLE_STATUSES = {SubmissionStatus.DRAFT, SubmissionStatus.CORRECTION_REQUIRED}

# Declarative workflow state machine.
# action name -> (statuses the submission may currently be in, target status)
WORKFLOW_TRANSITIONS: dict[
    str, tuple[tuple[SubmissionStatus, ...], SubmissionStatus]
] = {
    "submit": ((SubmissionStatus.DRAFT,), SubmissionStatus.SUBMITTED),
    # RESUBMITTED is also accepted so corrected data re-enters review.
    "review": (
        (SubmissionStatus.SUBMITTED, SubmissionStatus.RESUBMITTED),
        SubmissionStatus.UNDER_REVIEW,
    ),
    "request-correction": (
        (SubmissionStatus.UNDER_REVIEW,),
        SubmissionStatus.CORRECTION_REQUIRED,
    ),
    "resubmit": (
        (SubmissionStatus.CORRECTION_REQUIRED,),
        SubmissionStatus.RESUBMITTED,
    ),
    "approve": (
        (SubmissionStatus.UNDER_REVIEW, SubmissionStatus.RESUBMITTED),
        SubmissionStatus.APPROVED,
    ),
    "lock": ((SubmissionStatus.APPROVED,), SubmissionStatus.LOCKED),
}


def _apply_transition(
    submission_id: uuid.UUID,
    action: str,
    comments: Optional[str],
    db: Session,
    current_user: User,
) -> ApprovalWorkflow:
    """Validate the current status, move the submission, and audit the change.

    Raises HTTP 404 if the submission does not exist and HTTP 400 if the
    submission is not in one of the statuses allowed for this action.
    """
    allowed_from, to_status = WORKFLOW_TRANSITIONS[action]

    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status not in allowed_from:
        expected = " or ".join(s.value for s in allowed_from)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot {action} a submission in {submission.status.value} status. "
                f"Expected current status: {expected}."
            ),
        )

    from_status = submission.status
    submission.status = to_status

    entry = ApprovalWorkflow(
        submission_id=submission.id,
        from_status=from_status,
        to_status=to_status,
        action_by_id=current_user.id,
        comments=comments,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/", response_model=SubmissionResponse, status_code=status.HTTP_201_CREATED)
def create_submission(
    payload: SubmissionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new DRAFT submission."""
    # Validate referenced entities exist
    if not db.query(Project).filter_by(id=payload.project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    if not db.query(ReportingPeriod).filter_by(id=payload.reporting_period_id).first():
        raise HTTPException(status_code=404, detail="Reporting period not found")
    if not db.query(BRSRFramework).filter_by(id=payload.framework_id).first():
        raise HTTPException(status_code=404, detail="Framework not found")

    submission = Submission(
        project_id=payload.project_id,
        reporting_period_id=payload.reporting_period_id,
        framework_id=payload.framework_id,
        comments=payload.comments,
        status=SubmissionStatus.DRAFT,
        created_by_id=current_user.id,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


@router.get("/", response_model=List[SubmissionResponse])
def list_submissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return submissions accessible to the authenticated user."""
    return db.query(Submission).all()


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single submission by ID."""
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission


@router.post(
    "/{submission_id}/values",
    response_model=SubmissionValueResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_submission_value(
    submission_id: uuid.UUID,
    payload: SubmissionValueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or update an answer for a BRSR question within a submission."""
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    if submission.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit submission in {submission.status.value} status. "
                   f"Only DRAFT or CORRECTION_REQUIRED submissions can be edited.",
        )

    if not db.query(BRSRQuestion).filter_by(id=payload.question_id).first():
        raise HTTPException(status_code=404, detail="Question not found")

    # Upsert: update existing value or create new
    existing = (
        db.query(SubmissionValue)
        .filter_by(submission_id=submission_id, question_id=payload.question_id)
        .first()
    )

    if existing:
        existing.value_text = payload.value_text
        existing.value_numeric = payload.value_numeric
        existing.value_json = payload.value_json
        existing.data_source = payload.data_source
        existing.calculation_method = payload.calculation_method
        existing.source_department = payload.source_department
        db.commit()
        db.refresh(existing)
        return existing

    value = SubmissionValue(
        submission_id=submission_id,
        question_id=payload.question_id,
        value_text=payload.value_text,
        value_numeric=payload.value_numeric,
        value_json=payload.value_json,
        data_source=payload.data_source,
        calculation_method=payload.calculation_method,
        source_department=payload.source_department,
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


@router.get("/{submission_id}/values", response_model=List[SubmissionValueResponse])
def list_submission_values(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all submitted answers for a submission."""
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return db.query(SubmissionValue).filter_by(submission_id=submission_id).all()


# ── Workflow transitions ──
# Each endpoint delegates to _apply_transition, which owns status validation,
# the status update, and the ApprovalWorkflow audit row.

@router.post("/{submission_id}/submit", response_model=SubmissionWorkflowResponse)
def submit_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """DRAFT -> SUBMITTED. Hand the draft over for review."""
    return _apply_transition(submission_id, "submit", payload.comments, db, current_user)


@router.post("/{submission_id}/review", response_model=SubmissionWorkflowResponse)
def review_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """SUBMITTED -> UNDER_REVIEW. A reviewer picks the submission up."""
    return _apply_transition(submission_id, "review", payload.comments, db, current_user)


@router.post(
    "/{submission_id}/request-correction",
    response_model=SubmissionWorkflowResponse,
)
def request_correction(
    submission_id: uuid.UUID,
    payload: RequestCorrectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """UNDER_REVIEW -> CORRECTION_REQUIRED. A reason is mandatory."""
    if not payload.comments.strip():
        raise HTTPException(
            status_code=400,
            detail="A reason (comments) is required to request a correction.",
        )
    return _apply_transition(
        submission_id, "request-correction", payload.comments, db, current_user
    )


@router.post("/{submission_id}/resubmit", response_model=SubmissionWorkflowResponse)
def resubmit_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CORRECTION_REQUIRED -> RESUBMITTED. Corrections have been applied."""
    return _apply_transition(submission_id, "resubmit", payload.comments, db, current_user)


@router.post("/{submission_id}/approve", response_model=SubmissionWorkflowResponse)
def approve_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """UNDER_REVIEW or RESUBMITTED -> APPROVED."""
    return _apply_transition(submission_id, "approve", payload.comments, db, current_user)


@router.post("/{submission_id}/lock", response_model=SubmissionWorkflowResponse)
def lock_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """APPROVED -> LOCKED. Finalise the submission so it can no longer be edited."""
    return _apply_transition(submission_id, "lock", payload.comments, db, current_user)


@router.get(
    "/{submission_id}/workflow",
    response_model=List[SubmissionWorkflowResponse],
)
def list_submission_workflow(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the full audit trail of status transitions, oldest first."""
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return (
        db.query(ApprovalWorkflow)
        .filter_by(submission_id=submission_id)
        .order_by(ApprovalWorkflow.created_at, ApprovalWorkflow.id)
        .all()
    )
