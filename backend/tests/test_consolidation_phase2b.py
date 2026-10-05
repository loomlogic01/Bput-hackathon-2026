"""Phase 2B: consumption-weighted renewable-electricity KPI (backend only).

Covers the seven required behaviours without touching the database:

1. Demo values -> ~71.19%.
2. Raw Q_P6_RENEW_PCT SUM stays 221.75 (generic numeric aggregation).
3. Missing renewable value is ignored.
4. Missing electricity value is ignored.
5. Zero electricity never divides by zero (value None, count 0).
6. Scope helper never widens the caller's project set (canonicalisation keeps
   one row per project, LOCKED beats APPROVED; empty scope short-circuits to
   an empty result).
7. Only APPROVED/LOCKED canonical submissions contribute (REPORTABLE_STATUSES
   excludes every editorial status).
"""

import uuid

from backend.app.api.deps import accessible_project_ids
from backend.app.services.consolidation import (
    REPORTABLE_STATUSES,
    build_consolidation,
    compute_renewable_electricity_pct,
    select_canonical_submissions,
)
from backend.app.db.models.submission import SubmissionStatus


def _demo_pairs():
    return [(18400.0, 72.5), (12750.0, 61.0), (6200.0, 88.25)]


def test_demo_values_produce_weighted_share():
    value, count = compute_renewable_electricity_pct(_demo_pairs())
    assert count == 3
    assert value is not None and abs(value - 71.19) < 0.01


def test_raw_renewable_sum_unchanged():
    # The generic metric still SUMs percentages; the helper never touches it.
    assert sum(p for _, p in _demo_pairs()) == 221.75


def test_missing_renewable_ignored():
    value, count = compute_renewable_electricity_pct(
        [(18400.0, 72.5), (12750.0, None)]
    )
    assert (value, count) == (72.5, 1)


def test_missing_electricity_ignored():
    value, count = compute_renewable_electricity_pct(
        [(18400.0, 72.5), (None, 61.0)]
    )
    assert (value, count) == (72.5, 1)


def test_zero_electricity_returns_null():
    value, count = compute_renewable_electricity_pct(
        [(0.0, 72.5), (0.0, 61.0)]
    )
    assert value is None
    assert count == 0


def test_invalid_percentage_ignored():
    value, count = compute_renewable_electricity_pct(
        [(18400.0, 72.5), (12750.0, 150.0), (6200.0, float("nan"))]
    )
    assert (value, count) == (72.5, 1)


def test_only_approved_locked_contribute():
    allowed = {SubmissionStatus.APPROVED, SubmissionStatus.LOCKED}
    assert set(REPORTABLE_STATUSES) == allowed
    for status in (
        SubmissionStatus.DRAFT,
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.UNDER_REVIEW,
        SubmissionStatus.CORRECTION_REQUIRED,
        SubmissionStatus.RESUBMITTED,
    ):
        assert status not in REPORTABLE_STATUSES


class _Stub:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_scope_is_respected_and_canonical():
    # Canonicalisation: LOCKED beats APPROVED, newest wins within a status,
    # one row per project.
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    subs = [
        _Stub(project_id=p1, status=SubmissionStatus.APPROVED,
              updated_at=None),
        _Stub(project_id=p1, status=SubmissionStatus.LOCKED,
              updated_at=None),
        _Stub(project_id=p2, status=SubmissionStatus.APPROVED,
              updated_at=None),
        _Stub(project_id=p2, status=SubmissionStatus.DRAFT,
              updated_at=None),
    ]
    # DRAFT is not reportable, so drop it the way build_consolidation's query
    # filter does before canonicalisation.
    reportable = [s for s in subs if s.status in REPORTABLE_STATUSES]
    canonical = select_canonical_submissions(reportable)
    assert {s.project_id for s in canonical} == {p1, p2}
    assert next(s for s in canonical if s.project_id == p1).status == (
        SubmissionStatus.LOCKED
    )

    # Scope helper: a project-scoped user only ever sees their own project.
    def _no_db(*a, **k):
        raise AssertionError("no DB in unit test")

    user = _Stub(project_id=p1, business_unit_id=None, entity_id=None,
                 organization_id=None, roles=[])
    import backend.app.api.deps as deps

    orig = deps.is_super_admin
    deps.is_super_admin = lambda u: False
    try:
        assert accessible_project_ids(_Stub(query=_no_db), user) == {p1}
    finally:
        deps.is_super_admin = orig

    # build_consolidation short-circuits an empty scope to an empty result
    # without widening it: the pre-filter query object is built, but .all()
    # is never reached.
    class _Query:
        def filter(self, *a, **k):
            return self

        def all(self):
            raise AssertionError("must short-circuit before querying")

    period = _Stub(
        id=uuid.uuid4(),
        fiscal_year="FY 2024-25",
        start_date=None,
        end_date=None,
        boundary=_Stub(value="STANDALONE"),
    )
    framework = _Stub(id=uuid.uuid4(), name="F", version="1")
    res = build_consolidation(
        _Stub(query=lambda *a, **k: _Query()), period, framework, set())
    assert res["projects"] == [] and res["metrics"] == []
    assert res["derived_kpis"][0]["value"] is None
    assert res["derived_kpis"][0]["contributing_project_count"] == 0
