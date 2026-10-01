"""
BRSR Framework read endpoints.
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from backend.app.api.deps import get_current_user
from backend.app.api.v1.schemas import (
    BRSRFrameworkDetailResponse,
    BRSRFrameworkListResponse,
)
from backend.app.db.database import get_db
from backend.app.db.models.brsr import (
    BRSRFramework,
    BRSRIndicator,
    BRSRPrinciple,
    BRSRSection,
)
from backend.app.db.models.user import User

router = APIRouter()


@router.get("/", response_model=List[BRSRFrameworkListResponse])
def list_frameworks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active BRSR frameworks."""
    return db.query(BRSRFramework).filter_by(is_active=True).all()


@router.get("/{framework_id}", response_model=BRSRFrameworkDetailResponse)
def get_framework(
    framework_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single framework with its full section/principle/indicator/question hierarchy."""
    framework = (
        db.query(BRSRFramework)
        .options(
            joinedload(BRSRFramework.sections)
            .joinedload(BRSRSection.principles)
            .joinedload(BRSRPrinciple.indicators)
            .joinedload(BRSRIndicator.questions),
            joinedload(BRSRFramework.sections)
            .joinedload(BRSRSection.indicators)
            .joinedload(BRSRIndicator.questions),
        )
        .filter_by(id=framework_id)
        .first()
    )
    if not framework:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Framework not found",
        )
    return framework
