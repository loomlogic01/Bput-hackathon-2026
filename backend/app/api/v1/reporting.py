"""
Reporting & consolidation endpoints.

Read-only: every route here queries and returns. Nothing is written, so these
endpoints are safe to poll. Authorisation reuses the existing dependency set -
no new permission is introduced, and the caller's project scope is resolved
with the same helper the submission endpoints use.
"""

import io
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
from backend.app.services.pdf_report import generate_consolidation_pdf

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


@router.get("/consolidation/pdf")
def get_consolidation_pdf(
    reporting_period_id: uuid.UUID,
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return a PDF rendering of the consolidated ESG report.

    Identical authentication, project-scope, and 404 behaviour as
    ``GET /consolidation``.  The PDF is generated in-process from the same
    ``ConsolidationResponse`` that the JSON endpoint returns, so there is
    no duplicated aggregation logic.
    """
    reporting_period = (
        db.query(ReportingPeriod).filter_by(id=reporting_period_id).first()
    )
    if reporting_period is None:
        raise HTTPException(status_code=404, detail="Reporting period not found")

    framework = db.query(BRSRFramework).filter_by(id=framework_id).first()
    if framework is None:
        raise HTTPException(status_code=404, detail="Framework not found")

    scope = accessible_project_ids(db, current_user)
    consolidation_data: ConsolidationResponse = build_consolidation(
        db, reporting_period, framework, scope
    )

    pdf_bytes = generate_consolidation_pdf(consolidation_data)

    filename = (
        f"brsr_esg_{reporting_period.fiscal_year.replace('/', '-')}"
        f"_{framework.name.replace(' ', '_')}.pdf"
    )
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )