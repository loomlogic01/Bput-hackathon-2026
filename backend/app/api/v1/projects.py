"""
Project and Reporting Period read endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import (
    PERM_READ,
    accessible_organization_ids,
    accessible_project_ids,
    require_permissions,
)
from backend.app.api.v1.schemas import ProjectResponse, ReportingPeriodResponse
from backend.app.db.database import get_db
from backend.app.db.models.organization import Project
from backend.app.db.models.reporting import ReportingPeriod
from backend.app.db.models.user import User

router = APIRouter()


@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return the projects within the caller's organisational scope."""
    project_ids = accessible_project_ids(db, current_user)
    if project_ids is None:  # SUPER_ADMIN: unrestricted
        return db.query(Project).all()
    if not project_ids:  # assigned to nothing -> sees nothing
        return []
    return db.query(Project).filter(Project.id.in_(project_ids)).all()


@router.get("/reporting-periods", response_model=List[ReportingPeriodResponse])
def list_reporting_periods(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return the reporting periods within the caller's organisational scope."""
    org_ids = accessible_organization_ids(db, current_user)
    if org_ids is None:  # SUPER_ADMIN: unrestricted
        return db.query(ReportingPeriod).all()
    if not org_ids:
        return []
    return (
        db.query(ReportingPeriod)
        .filter(ReportingPeriod.organization_id.in_(org_ids))
        .all()
    )
