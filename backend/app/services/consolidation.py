"""
Consolidation service: request-time aggregation of approved BRSR submissions.

Design constraints, all deliberate:

* **Read-only.** Nothing here writes, commits, or mutates a row.
* **Only APPROVED/LOCKED submissions contribute.** Anything still in an
  editorial state is invisible, so a consolidation can never leak draft data.
* **One canonical submission per project.** Several submissions may exist for
  the same project/period/framework; LOCKED beats APPROVED, and within a status
  the most recently updated one wins. Without this a project is counted twice.
* **Only NUMBER questions, and only value_numeric.** TEXT/BOOLEAN/SELECT/TABLE
  are not summable, and the API does not validate response_type on write, so
  this filter is the only guard against summing a string.
* **Grouped strictly by question.** Two questions are never merged, even when
  their unit_of_measurement strings happen to match.
* **Scope is enforced by the caller.** The service receives an already-resolved
  set of project ids and never widens it.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set

from sqlalchemy.orm import Session

from backend.app.db.models.brsr import (
    BRSRFramework,
    BRSRQuestion,
    QuestionResponseType,
)
from backend.app.db.models.organization import (
    BusinessUnit,
    Entity,
    Organization,
    Project,
)
from backend.app.db.models.reporting import ReportingPeriod
from backend.app.db.models.submission import (
    Submission,
    SubmissionStatus,
    SubmissionValue,
)

# Statuses whose values are stable enough to report on.
REPORTABLE_STATUSES = (SubmissionStatus.APPROVED, SubmissionStatus.LOCKED)

# LOCKED outranks APPROVED when a project has both.
_STATUS_RANK = {
    SubmissionStatus.LOCKED: 0,
    SubmissionStatus.APPROVED: 1,
}


def _as_utc(value: Optional[datetime]) -> datetime:
    """Sort key for updated_at; naive DB timestamps are treated as UTC."""
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def select_canonical_submissions(
    submissions: Sequence[Submission],
) -> List[Submission]:
    """Reduce candidate submissions to exactly one per project.

    LOCKED wins over APPROVED; ties on status are broken by the newest
    ``updated_at``. Ordered by project id so the response is stable.
    """
    best: Dict[uuid.UUID, Submission] = {}
    for submission in submissions:
        current = best.get(submission.project_id)
        if current is None:
            best[submission.project_id] = submission
            continue
        current_rank = _STATUS_RANK[current.status]
        candidate_rank = _STATUS_RANK[submission.status]
        if candidate_rank < current_rank:
            # A strictly better status always wins, however old it is.
            best[submission.project_id] = submission
        elif candidate_rank == current_rank and _as_utc(
            submission.updated_at
        ) > _as_utc(current.updated_at):
            # Same status: newest wins.
            best[submission.project_id] = submission
    return [best[pid] for pid in sorted(best, key=str)]


def _project_hierarchy(project: Project) -> Dict[str, object]:
    """Flatten Organization -> Entity -> BusinessUnit -> Project for one row.

    Walks the existing relationships; a missing link degrades to None rather
    than raising, so a partially populated hierarchy still reports.
    """
    business_unit: Optional[BusinessUnit] = project.business_unit
    entity: Optional[Entity] = business_unit.entity if business_unit else None
    organization: Optional[Organization] = entity.organization if entity else None
    return {
        "organization_id": organization.id if organization else None,
        "organization_name": organization.name if organization else None,
        "organization_code": organization.code if organization else None,
        "entity_id": entity.id if entity else None,
        "entity_name": entity.name if entity else None,
        "entity_code": entity.code if entity else None,
        "business_unit_id": business_unit.id if business_unit else None,
        "business_unit_name": business_unit.name if business_unit else None,
        "business_unit_code": business_unit.code if business_unit else None,
        "project_id": project.id,
        "project_name": project.name,
        "project_code": project.code,
    }


def _question_metadata(question: BRSRQuestion) -> Dict[str, object]:
    """Section / indicator / principle labels for one question.

    ``principle_*`` is None for Section A/B indicators, which have no principle.
    """
    indicator = question.indicator
    section = indicator.section if indicator else None
    principle = indicator.principle if indicator else None
    return {
        "question_id": question.id,
        "question_code": question.code,
        "question_text": question.question_text,
        "unit_of_measurement": question.unit_of_measurement,
        "is_mandatory": question.is_mandatory,
        "section_code": section.code if section else None,
        "section_title": section.title if section else None,
        "indicator_code": indicator.code if indicator else None,
        "indicator_title": indicator.title if indicator else None,
        "indicator_type": (
            indicator.indicator_type.value
            if indicator and indicator.indicator_type
            else None
        ),
        "principle_code": principle.code if principle else None,
        "principle_title": principle.title if principle else None,
    }


def _period_summary(period: ReportingPeriod) -> Dict[str, object]:
    return {
        "id": period.id,
        "fiscal_year": period.fiscal_year,
        "start_date": period.start_date,
        "end_date": period.end_date,
        "boundary": period.boundary.value if period.boundary else None,
    }


def _empty_result(
    reporting_period: ReportingPeriod, framework: BRSRFramework
) -> Dict[str, object]:
    """A valid request with nothing reportable still answers 200."""
    return {
        "reporting_period": _period_summary(reporting_period),
        "framework": {
            "id": framework.id,
            "name": framework.name,
            "version": framework.version,
        },
        "projects": [],
        "metrics": [],
        "totals": {"projects_contributing": 0, "metrics_aggregated": 0},
    }


def build_consolidation(
    db: Session,
    reporting_period: ReportingPeriod,
    framework: BRSRFramework,
    scoped_project_ids: Optional[Set[uuid.UUID]],
) -> Dict[str, object]:
    """Aggregate NUMBER answers across the caller's approved submissions.

    ``scoped_project_ids`` of ``None`` means unrestricted (SUPER_ADMIN),
    matching the existing list endpoints. An empty set means the caller can
    reach nothing, which yields an empty result rather than an error.
    """
    query = db.query(Submission).filter(
        Submission.reporting_period_id == reporting_period.id,
        Submission.framework_id == framework.id,
        Submission.status.in_(REPORTABLE_STATUSES),
    )
    if scoped_project_ids is not None:
        if not scoped_project_ids:
            return _empty_result(reporting_period, framework)
        query = query.filter(Submission.project_id.in_(scoped_project_ids))

    canonical = select_canonical_submissions(query.all())
    if not canonical:
        return _empty_result(reporting_period, framework)

    submission_ids = [s.id for s in canonical]
    project_by_submission = {s.id: s.project_id for s in canonical}

    # Only NUMBER rows carrying a real number. The response_type filter is the
    # contract that keeps TEXT/BOOLEAN/SELECT/TABLE out; the null filter drops
    # blank and non-numeric entries.
    rows = (
        db.query(SubmissionValue, BRSRQuestion)
        .join(BRSRQuestion, SubmissionValue.question_id == BRSRQuestion.id)
        .filter(
            SubmissionValue.submission_id.in_(submission_ids),
            BRSRQuestion.response_type == QuestionResponseType.NUMBER,
            SubmissionValue.value_numeric.isnot(None),
        )
        .all()
    )

    totals: Dict[uuid.UUID, float] = {}
    projects: Dict[uuid.UUID, Set[uuid.UUID]] = {}
    questions: Dict[uuid.UUID, BRSRQuestion] = {}
    for value, question in rows:
        totals[question.id] = totals.get(question.id, 0.0) + float(value.value_numeric)
        projects.setdefault(question.id, set()).add(
            project_by_submission[value.submission_id]
        )
        questions[question.id] = question

    metrics = []
    ordered = sorted(
        questions.values(),
        key=lambda q: (q.indicator.section.order_index if q.indicator and q.indicator.section else 0,
                       q.indicator.order_index if q.indicator else 0,
                       q.order_index),
    )
    for question in ordered:
        contributing = projects[question.id]
        metrics.append(
            {
                **_question_metadata(question),
                "aggregated_value": totals[question.id],
                "contributing_project_count": len(contributing),
                "contributing_project_ids": sorted(contributing, key=str),
            }
        )

    project_rows = []
    for submission in canonical:
        project = db.query(Project).filter_by(id=submission.project_id).first()
        if project is None:
            continue
        project_rows.append(
            {
                **_project_hierarchy(project),
                "submission_id": submission.id,
                "submission_status": submission.status.value,
            }
        )

    return {
        "reporting_period": _period_summary(reporting_period),
        "framework": {
            "id": framework.id,
            "name": framework.name,
            "version": framework.version,
        },
        "projects": project_rows,
        "metrics": metrics,
        "totals": {
            "projects_contributing": len(project_rows),
            "metrics_aggregated": len(metrics),
        },
    }