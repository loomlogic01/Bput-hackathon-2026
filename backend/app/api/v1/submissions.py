"""
Submission and SubmissionValue CRUD endpoints.
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    PERM_APPROVE,
    PERM_CREATE,
    PERM_READ,
    PERM_REVIEW,
    PERM_SUBMIT,
    PERM_UPDATE,
    accessible_project_ids,
    ensure_project_access,
    require_permissions,
)
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
from backend.app.db.models.brsr import (
    BRSRFramework,
    BRSRIndicator,
    BRSRQuestion,
    BRSRSection,
)
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


def load_scoped_submission(
    submission_id: uuid.UUID, db: Session, current_user: User
) -> Submission:
    """Load a submission, enforcing that it exists and is in the caller's scope.

    Raises 404 when the submission genuinely does not exist, and 403 when it
    exists but belongs to a project outside the caller's scope.
    """
    submission = db.query(Submission).filter_by(id=submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    ensure_project_access(db, current_user, submission.project_id)
    return submission


def _guard_transition(submission: Submission, action: str) -> None:
    """Reject a transition the state machine does not allow.

    Extracted verbatim from _apply_transition so `submit` can run the same
    status check *before* validating mandatory questions. Without this, an
    already-submitted submission would report unanswered questions instead of
    the existing "Cannot submit..." error.
    """
    allowed_from, _ = WORKFLOW_TRANSITIONS[action]
    if submission.status not in allowed_from:
        expected = " or ".join(s.value for s in allowed_from)
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot {action} a submission in {submission.status.value} status. "
                f"Expected current status: {expected}."
            ),
        )


def _apply_transition(
    submission_id: uuid.UUID,
    action: str,
    comments: Optional[str],
    db: Session,
    current_user: User,
) -> ApprovalWorkflow:
    """Validate scope and status, move the submission, and audit the change.

    Raises HTTP 404 if the submission does not exist, 403 if it is outside the
    caller's scope, and 400 if its status does not allow this action.
    """
    allowed_from, to_status = WORKFLOW_TRANSITIONS[action]
    submission = load_scoped_submission(submission_id, db, current_user)
    _guard_transition(submission, action)

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
    current_user: User = Depends(require_permissions(PERM_CREATE)),
):
    """Create a new DRAFT submission for a project in the caller's scope."""
    # Validate referenced entities exist
    if not db.query(Project).filter_by(id=payload.project_id).first():
        raise HTTPException(status_code=404, detail="Project not found")
    if not db.query(ReportingPeriod).filter_by(id=payload.reporting_period_id).first():
        raise HTTPException(status_code=404, detail="Reporting period not found")
    if not db.query(BRSRFramework).filter_by(id=payload.framework_id).first():
        raise HTTPException(status_code=404, detail="Framework not found")

    # ...and that the caller is allowed to file against this project.
    ensure_project_access(db, current_user, payload.project_id)

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
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return the submissions within the caller's organisational scope."""
    project_ids = accessible_project_ids(db, current_user)
    if project_ids is None:  # SUPER_ADMIN: unrestricted
        return db.query(Submission).all()
    if not project_ids:
        return []
    return db.query(Submission).filter(Submission.project_id.in_(project_ids)).all()


@router.get("/{submission_id}", response_model=SubmissionResponse)
def get_submission(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return a single submission by ID, if it is in the caller's scope."""
    return load_scoped_submission(submission_id, db, current_user)


@router.post(
    "/{submission_id}/values",
    response_model=SubmissionValueResponse,
    status_code=status.HTTP_201_CREATED,
)
def upsert_submission_value(
    submission_id: uuid.UUID,
    payload: SubmissionValueCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_UPDATE)),
):
    """Create or update an answer for a BRSR question within a submission."""
    submission = load_scoped_submission(submission_id, db, current_user)

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
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return all submitted answers for a submission in the caller's scope."""
    load_scoped_submission(submission_id, db, current_user)
    return db.query(SubmissionValue).filter_by(submission_id=submission_id).all()


def _has_meaningful_value(value: Optional[SubmissionValue]) -> bool:
    """True when a stored answer actually carries data.

    The values endpoint accepts a row whose three value columns are all NULL,
    so the existence of a SubmissionValue does not by itself mean the question
    was answered.
    """
    if value is None:
        return False
    if value.value_numeric is not None:
        return True
    if value.value_text is not None and value.value_text.strip():
        return True
    if value.value_json:
        return True
    return False


def _missing_mandatory_questions(
    db: Session, submission: Submission
) -> List[dict]:
    """Mandatory questions in this submission's framework with no usable answer.

    Scoped question -> indicator -> section -> framework, so questions that
    belong to another framework can never block this submission. Ordering is
    by section, then indicator, then question so the error list is stable.
    """
    mandatory = (
        db.query(BRSRQuestion)
        .join(BRSRIndicator, BRSRQuestion.indicator_id == BRSRIndicator.id)
        .join(BRSRSection, BRSRIndicator.section_id == BRSRSection.id)
        .filter(
            BRSRSection.framework_id == submission.framework_id,
            BRSRQuestion.is_mandatory.is_(True),
        )
        .order_by(
            BRSRSection.order_index,
            BRSRIndicator.order_index,
            BRSRQuestion.order_index,
        )
        .all()
    )
    if not mandatory:
        return []

    answered = {
        v.question_id
        for v in db.query(SubmissionValue)
        .filter_by(submission_id=submission.id)
        .all()
        if _has_meaningful_value(v)
    }

    return [
        {
            "question_id": str(q.id),
            "code": q.code,
            "question": q.question_text,
        }
        for q in mandatory
        if q.id not in answered
    ]


def _require_mandatory_answers(db: Session, submission: Submission) -> None:
    """Reject a handover while mandatory questions are unanswered.

    Shared by /submit and /resubmit so both enforce exactly the same rules and
    return exactly the same structured 400. All completeness logic lives in
    _missing_mandatory_questions; this only raises, so there is one
    implementation and one error shape.
    """
    missing = _missing_mandatory_questions(db, submission)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Submission has unanswered mandatory questions.",
                "missing_questions": missing,
            },
        )


# ── Workflow transitions ──
# Each endpoint delegates to _apply_transition, which owns status validation,
# the status update, and the ApprovalWorkflow audit row.

@router.post("/{submission_id}/submit", response_model=SubmissionWorkflowResponse)
def submit_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_SUBMIT)),
):
    """DRAFT -> SUBMITTED, once every mandatory question is answered."""
    # Scope and status are checked first, so an out-of-scope submission still
    # 403s and a non-DRAFT submission still returns the existing
    # "Cannot submit..." 400 rather than a validation error.
    submission = load_scoped_submission(submission_id, db, current_user)
    _guard_transition(submission, "submit")
    _require_mandatory_answers(db, submission)

    return _apply_transition(submission_id, "submit", payload.comments, db, current_user)


@router.post("/{submission_id}/review", response_model=SubmissionWorkflowResponse)
def review_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_REVIEW)),
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
    current_user: User = Depends(require_permissions(PERM_REVIEW)),
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
    current_user: User = Depends(require_permissions(PERM_SUBMIT)),
):
    """CORRECTION_REQUIRED -> RESUBMITTED, once corrections are complete.

    The same mandatory-question validation as /submit. Without it, a value
    blanked during CORRECTION_REQUIRED could reach RESUBMITTED - and therefore
    APPROVED - while incomplete.
    """
    # Scope and status first, so an out-of-scope submission still 403s and a
    # non-CORRECTION_REQUIRED one still returns the existing status 400.
    submission = load_scoped_submission(submission_id, db, current_user)
    _guard_transition(submission, "resubmit")
    _require_mandatory_answers(db, submission)

    return _apply_transition(submission_id, "resubmit", payload.comments, db, current_user)


@router.post("/{submission_id}/approve", response_model=SubmissionWorkflowResponse)
def approve_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_APPROVE)),
):
    """UNDER_REVIEW or RESUBMITTED -> APPROVED."""
    return _apply_transition(submission_id, "approve", payload.comments, db, current_user)


@router.post("/{submission_id}/lock", response_model=SubmissionWorkflowResponse)
def lock_submission(
    submission_id: uuid.UUID,
    payload: WorkflowActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_APPROVE)),
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
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return the full audit trail of status transitions, oldest first."""
    load_scoped_submission(submission_id, db, current_user)
    return (
        db.query(ApprovalWorkflow)
        .filter_by(submission_id=submission_id)
        .order_by(ApprovalWorkflow.created_at, ApprovalWorkflow.id)
        .all()
    )
