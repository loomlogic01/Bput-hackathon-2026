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


def _order(collection):
    """Sort an eager-loaded collection by order_index, then code for stability."""
    collection[:] = sorted(collection, key=lambda obj: (obj.order_index, obj.code))


def _sort_hierarchy(framework):
    """Order every level of the BRSR hierarchy by order_index.

    SQLAlchemy 2.1 exposes no ordering option for eager-loaded relationships
    (Load.order_by was removed), so the loaded collections are sorted here.
    In-place slice assignment avoids triggering a flush; no data is modified.
    """
    _order(framework.sections)
    for section in framework.sections:
        _order(section.principles)
        _order(section.indicators)
        for principle in section.principles:
            _order(principle.indicators)
            for indicator in principle.indicators:
                _order(indicator.questions)


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
    _sort_hierarchy(framework)
    return framework
