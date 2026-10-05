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
* **SUM semantics are never silently changed.** ``aggregated_value`` stays the
  raw SUM of ``value_numeric``. Where a SUM is arithmetically right but
  analytically meaningless - a percentage - the metric is flagged
  (``aggregated_value_is_meaningful: false``) and the defensible figure is
  published separately under ``derived_kpis``. The raw sum is still returned so
  existing consumers keep working.
* **Derived KPIs only combine what is actually present.** A project counts only
  if it has both a positive finite basis value and a finite percentage in
  [0, 100]; otherwise it is skipped, never estimated. With nothing valid to
  divide by the KPI keeps ``value=None`` and ``contributing_project_count=0``
  instead of being reported as zero.
* **Scope is enforced by the caller.** The service receives an already-resolved
  set of project ids and never widens it.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Set

from sqlalchemy.orm import Session

from backend.app.db.models.brsr import (
    BRSRFramework,
    BRSRIndicator,
    BRSRQuestion,
    BRSRSection,
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

# Consolidated figures that cannot be obtained by summing.
#
# Questions are referenced by CODE and resolved against the requested framework
# at request time, so no UUID is ever hard-coded and the definition survives a
# reseed with different primary keys.
#
#   basis_question_code   the additive quantity used as the weight (here, MWh)
#   percent_question_code the per-project share that must NOT be summed
#
# The published value is
#   sum(electricity_i * pct_i / 100) / sum(electricity_i) * 100
# i.e. consumption-weighted, which is the only defensible way to combine
# percentages across different-sized sites.
DERIVED_KPIS = (
    {
        "code": "P6_RENEWABLE_ELECTRICITY_PCT",
        "label": "Renewable electricity consumption percentage",
        "unit": "%",
        "calculation_method": "consumption-weighted",
        "basis_question_code": "Q_P6_ELEC_CONS",
        "percent_question_code": "Q_P6_RENEW_PCT",
    },
)

# Question codes whose raw SUM is arithmetically right but analytically
# meaningless. Their metrics are flagged so a client cannot display the sum as a
# consolidated percentage.
_PERCENT_CODES = frozenset(k["percent_question_code"] for k in DERIVED_KPIS)
# Maps a percent question code -> the derived KPI that supersedes it.
_SUPERSEDER = {
    k["percent_question_code"]: k["code"] for k in DERIVED_KPIS
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


def _question_by_code(
    db: Session, framework: BRSRFramework, code: str
) -> Optional[BRSRQuestion]:
    """Resolve one question of the requested framework by its code.

    Scoped to the framework so a same-coded question in another framework can
    never leak in.
    """
    return (
        db.query(BRSRQuestion)
        .join(BRSRIndicator, BRSRQuestion.indicator_id == BRSRIndicator.id)
        .join(BRSRSection, BRSRIndicator.section_id == BRSRSection.id)
        .filter(BRSRSection.framework_id == framework.id, BRSRQuestion.code == code)
        .first()
    )


def compute_renewable_electricity_pct(
    pairs: Sequence[tuple],
) -> tuple:
    """Consumption-weighted renewable share for (electricity, pct) pairs.

    Only pairs with a present, finite electricity value > 0 and a present,
    finite percentage in [0, 100] contribute; everything else is ignored.
    Returns ``(value, contributing_project_count)`` where ``value`` is None
    when nothing contributes (never a division-by-zero).
    """
    weighted_sum = 0.0
    basis_sum = 0.0
    used = 0
    for electricity, pct in pairs:
        if (
            electricity is None
            or pct is None
            or not math.isfinite(electricity)
            or not math.isfinite(pct)
            or electricity <= 0
            or pct < 0
            or pct > 100
        ):
            continue
        weighted_sum += electricity * (pct / 100.0)
        basis_sum += electricity
        used += 1
    if used and basis_sum > 0:
        return weighted_sum / basis_sum * 100.0, used
    return None, 0


def _compute_derived_kpis(
    db: Session,
    framework: BRSRFramework,
    per_project: Dict[uuid.UUID, Dict[uuid.UUID, float]],
) -> List[Dict[str, object]]:
    """Build the consolidated figures that SUM cannot express.

    One entry is always returned per spec in ``DERIVED_KPIS``. A project
    contributes only when it has BOTH a present, finite electricity value
    > 0 AND a present, finite renewable percentage in [0, 100]. Anything
    else is ignored, and with no valid contributor the entry keeps
    ``value=None`` and ``contributing_project_count=0`` rather than a
    division-by-zero.
    """
    out: List[Dict[str, object]] = []
    for spec in DERIVED_KPIS:
        basis = _question_by_code(db, framework, spec["basis_question_code"])
        percent = _question_by_code(db, framework, spec["percent_question_code"])
        entry: Dict[str, object] = {
            "code": spec["code"],
            "label": spec["label"],
            "unit": spec["unit"],
            "calculation_method": spec["calculation_method"],
            "source_question_codes": [
                spec["basis_question_code"],
                spec["percent_question_code"],
            ],
            "value": None,
            "contributing_project_count": 0,
        }
        if basis is None or percent is None:
            out.append(entry)
            continue

        basis_values = per_project.get(basis.id, {})
        percent_values = per_project.get(percent.id, {})

        pairs = [
            (electricity, percent_values.get(project_id))
            for project_id, electricity in basis_values.items()
        ]
        # Projects carrying only a percentage (no electricity row) never appear
        # in basis_values; scan them too so a missing-electricity project is
        # explicitly evaluated (and ignored) rather than silently absent.
        basis_ids = set(basis_values)
        for project_id, pct in percent_values.items():
            if project_id not in basis_ids:
                pairs.append((None, pct))
        value, used = compute_renewable_electricity_pct(pairs)
        if value is not None:
            entry["value"] = value
            entry["contributing_project_count"] = used
        out.append(entry)
    return out


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
        "derived_kpis": [
            {
                "code": spec["code"],
                "label": spec["label"],
                "unit": spec["unit"],
                "calculation_method": spec["calculation_method"],
                "source_question_codes": [
                    spec["basis_question_code"],
                    spec["percent_question_code"],
                ],
                "value": None,
                "contributing_project_count": 0,
            }
            for spec in DERIVED_KPIS
        ],
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
    # question_id -> {project_id: value_numeric}. Needed for the derived KPIs,
    # which combine per-project values rather than totals.
    per_project: Dict[uuid.UUID, Dict[uuid.UUID, float]] = {}
    for value, question in rows:
        project_id = project_by_submission[value.submission_id]
        number = float(value.value_numeric)
        totals[question.id] = totals.get(question.id, 0.0) + number
        projects.setdefault(question.id, set()).add(project_id)
        per_project.setdefault(question.id, {})[project_id] = number
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
        is_percent = question.code in _PERCENT_CODES
        metrics.append(
            {
                **_question_metadata(question),
                "aggregated_value": totals[question.id],
                "aggregation": "sum",
                "aggregated_value_is_meaningful": not is_percent,
                "superseded_by_derived_kpi": _SUPERSEDER.get(question.code),
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
        "derived_kpis": _compute_derived_kpis(db, framework, per_project),
        "totals": {
            "projects_contributing": len(project_rows),
            "metrics_aggregated": len(metrics),
        },
    }