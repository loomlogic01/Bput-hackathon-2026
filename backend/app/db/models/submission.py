"""
Submission, SubmissionValue, Evidence, and ApprovalWorkflow models.

Manages data entry, provenance, evidence attachments, and multi-stage review workflows
for BRSR reporting.
"""

import enum
import uuid
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin


class SubmissionStatus(str, enum.Enum):
    """
    Lifecycle stages for a BRSR submission.
    """

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
    RESUBMITTED = "RESUBMITTED"
    APPROVED = "APPROVED"
    LOCKED = "LOCKED"


class Submission(Base, UUIDMixin, TimestampMixin):
    """
    Container for a BRSR filing attempt for a given Project, ReportingPeriod, and Framework.
    """

    __tablename__ = "submissions"

    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status"),
        default=SubmissionStatus.DRAFT,
        nullable=False,
        index=True,
    )
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scoping links
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reporting_period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reporting_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brsr_frameworks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project")
    reporting_period: Mapped["ReportingPeriod"] = relationship("ReportingPeriod")
    framework: Mapped["BRSRFramework"] = relationship("BRSRFramework")
    created_by: Mapped[Optional["User"]] = relationship("User")

    @property
    def reporting_period_label(self) -> Optional[str]:
        """Display name of the linked reporting period, e.g. "FY 2025-26".

        A read-only convenience for API responses: a caller authorized to read
        this submission may see which period it covers, without needing access
        to the /projects/reporting-periods collection (which stays gated).
        Not a mapped column - no schema change.
        """
        period = self.reporting_period
        return period.fiscal_year if period is not None else None

    values: Mapped[List["SubmissionValue"]] = relationship(
        "SubmissionValue", back_populates="submission", cascade="all, delete-orphan"
    )
    workflow_actions: Mapped[List["ApprovalWorkflow"]] = relationship(
        "ApprovalWorkflow", back_populates="submission", cascade="all, delete-orphan"
    )
    evidences: Mapped[List["Evidence"]] = relationship(
        "Evidence", back_populates="submission", cascade="all, delete-orphan"
    )


class SubmissionValue(Base, UUIDMixin, TimestampMixin):
    """
    A single answer entered for a specific BRSR question within a submission.
    """

    __tablename__ = "submission_values"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brsr_questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    # Flexible data storage columns
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_numeric: Mapped[Optional[float]] = mapped_column(Float, nullable=True, index=True)
    value_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Data Provenance / Source Information
    data_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Electricity Meter #4"
    calculation_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # e.g. "GHG Protocol Scope 2"
    source_department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # e.g. "Facilities & EHS"

    # Relationships
    submission: Mapped["Submission"] = relationship("Submission", back_populates="values")
    question: Mapped["BRSRQuestion"] = relationship("BRSRQuestion")
    evidences: Mapped[List["Evidence"]] = relationship(
        "Evidence", back_populates="submission_value", cascade="all, delete-orphan"
    )


class Evidence(Base, UUIDMixin, TimestampMixin):
    """
    Attached supporting documents/files for verification and audit proof.
    """

    __tablename__ = "evidences"

    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)  # S3 key or local file path
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submission_value_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("submission_values.id", ondelete="CASCADE"), nullable=True, index=True
    )
    uploaded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    submission: Mapped["Submission"] = relationship("Submission", back_populates="evidences")
    submission_value: Mapped[Optional["SubmissionValue"]] = relationship(
        "SubmissionValue", back_populates="evidences"
    )
    uploaded_by: Mapped[Optional["User"]] = relationship("User")


class ApprovalWorkflow(Base, UUIDMixin, TimestampMixin):
    """
    Audit log of status changes and review feedback for a submission.
    """

    __tablename__ = "approval_workflows"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status"), nullable=False
    )
    to_status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status"), nullable=False
    )
    action_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    submission: Mapped["Submission"] = relationship(
        "Submission", back_populates="workflow_actions"
    )
    action_by: Mapped[Optional["User"]] = relationship("User")
