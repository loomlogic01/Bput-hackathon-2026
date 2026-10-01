"""
Project and Reporting Period read endpoints.
"""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.api.v1.schemas import ProjectResponse, ReportingPeriodResponse
from backend.app.db.database import get_db
from backend.app.db.models.organization import Project
from backend.app.db.models.reporting import ReportingPeriod
from backend.app.db.models.user import User

router = APIRouter()


@router.get("/", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all accessible projects."""
    return db.query(Project).all()


@router.get("/reporting-periods", response_model=List[ReportingPeriodResponse])
def list_reporting_periods(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all reporting periods."""
    return db.query(ReportingPeriod).all()
