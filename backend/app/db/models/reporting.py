"""
Reporting Period model.

Defines the fiscal time window and boundary type (STANDALONE / CONSOLIDATED)
for which ESG/BRSR data is collected and reported.
"""

import enum
import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin


class ReportingBoundary(str, enum.Enum):
    """
    Whether the report covers a single entity or the consolidated group.
    """

    STANDALONE = "STANDALONE"
    CONSOLIDATED = "CONSOLIDATED"


class ReportingPeriod(Base, UUIDMixin, TimestampMixin):
    """
    Represents a fiscal year / reporting window for ESG/BRSR data collection.

    Example:
        fiscal_year  = "FY 2024-25"
        start_date   = 2024-04-01
        end_date     = 2025-03-31
        boundary     = STANDALONE
    """

    __tablename__ = "reporting_periods"

    fiscal_year: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    boundary: Mapped[ReportingBoundary] = mapped_column(
        Enum(ReportingBoundary, name="reporting_boundary"),
        nullable=False,
        default=ReportingBoundary.STANDALONE,
    )
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Links this reporting period to a specific Organization
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
