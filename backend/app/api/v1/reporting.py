"""
Reporting & consolidation endpoints.

Read-only: every route here queries and returns. Nothing is written, so these
endpoints are safe to poll. Authorisation reuses the existing dependency set -
no new permission is introduced, and the caller's project scope is resolved
with the same helper the submission endpoints use.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    PERM_READ,
    accessible_project_ids,
    require_permissions,
)
from backend.app.api.v1.schemas import ConsolidationResponse
from backend.app.db.database import get_db
from backend.app.db.models.brsr import BRSRFramework
from backend.app.db.models.reporting import ReportingPeriod
from backend.app.db.models.user import User
from backend.app.services.consolidation import build_consolidation

router = APIRouter()


@router.get("/consolidation", response_model=ConsolidationResponse)
def get_consolidation(
    reporting_period_id: uuid.UUID,
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Aggregate NUMBER answers across the caller's approved/locked submissions.

    Requires the same `submission:read` permission as the submission endpoints.
    Only APPROVED and LOCKED submissions contribute, and exactly one canonical
    submission per project is counted (LOCKED wins, then newest updated_at).
    A valid request with nothing to report returns 200 with empty lists.
    """
    reporting_period = (
        db.query(ReportingPeriod).filter_by(id=reporting_period_id).first()
    )
    if reporting_period is None:
        raise HTTPException(status_code=404, detail="Reporting period not found")

    framework = db.query(BRSRFramework).filter_by(id=framework_id).first()
    if framework is None:
        raise HTTPException(status_code=404, detail="Framework not found")

    # Reuse the shared scope helper; None means unrestricted (SUPER_ADMIN),
    # exactly as list_projects and list_submissions behave.
    scope = accessible_project_ids(db, current_user)
    return build_consolidation(db, reporting_period, framework, scope)