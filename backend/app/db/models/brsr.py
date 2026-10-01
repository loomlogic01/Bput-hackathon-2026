"""
BRSR Metadata Models:
Framework -> Sections -> Principles -> Indicators -> Questions

Allows storing SEBI BRSR and BRSR Core as configurable database metadata,
enabling schema updates and multi-version framework management without code changes.
"""

import enum
import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin


class QuestionResponseType(str, enum.Enum):
    """Supported data entry input types for BRSR questions."""

    NUMBER = "NUMBER"
    TEXT = "TEXT"
    BOOLEAN = "BOOLEAN"
    SELECT = "SELECT"
    TABLE = "TABLE"


class IndicatorType(str, enum.Enum):
    """SEBI BRSR distinction between mandatory and voluntary disclosures."""

    ESSENTIAL = "ESSENTIAL"
    LEADERSHIP = "LEADERSHIP"


class BRSRFramework(Base, UUIDMixin, TimestampMixin):
    """
    Top-level standard version (e.g., 'SEBI BRSR Core', version '2023-24').
    """

    __tablename__ = "brsr_frameworks"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 1-to-many relationship with sections
    sections: Mapped[List["BRSRSection"]] = relationship(
        "BRSRSection", back_populates="framework", cascade="all, delete-orphan"
    )


class BRSRSection(Base, UUIDMixin, TimestampMixin):
    """
    Major sections of the BRSR standard:
    Section A (General), Section B (Management), Section C (Principles).
    """

    __tablename__ = "brsr_sections"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    framework_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brsr_frameworks.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    framework: Mapped["BRSRFramework"] = relationship(
        "BRSRFramework", back_populates="sections"
    )
    principles: Mapped[List["BRSRPrinciple"]] = relationship(
        "BRSRPrinciple", back_populates="section", cascade="all, delete-orphan"
    )
    # Direct indicators that belong to this section (owns the lifecycle of indicators)
    indicators: Mapped[List["BRSRIndicator"]] = relationship(
        "BRSRIndicator", back_populates="section", cascade="all, delete-orphan"
    )


class BRSRPrinciple(Base, UUIDMixin, TimestampMixin):
    """
    NGRBC Principles (Principles 1 through 9 under Section C).
    """

    __tablename__ = "brsr_principles"

    principle_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., 'P1', 'P2'
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brsr_sections.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    section: Mapped["BRSRSection"] = relationship(
        "BRSRSection", back_populates="principles"
    )
    # Optional parent relationship: does not own delete-orphan lifecycle
    indicators: Mapped[List["BRSRIndicator"]] = relationship(
        "BRSRIndicator", back_populates="principle"
    )


class BRSRIndicator(Base, UUIDMixin, TimestampMixin):
    """
    Category of indicators (Essential vs Leadership) under a Section and optionally a Principle.
    """

    __tablename__ = "brsr_indicators"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    indicator_type: Mapped[IndicatorType] = mapped_column(
        Enum(IndicatorType, name="indicator_type"),
        default=IndicatorType.ESSENTIAL,
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Required link to a Section (A, B, or C)
    section_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brsr_sections.id", ondelete="CASCADE"), nullable=False
    )
    # Optional link to a Principle (only for Section C indicators)
    principle_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("brsr_principles.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    section: Mapped["BRSRSection"] = relationship(
        "BRSRSection", back_populates="indicators"
    )
    principle: Mapped[Optional["BRSRPrinciple"]] = relationship(
        "BRSRPrinciple", back_populates="indicators"
    )
    questions: Mapped[List["BRSRQuestion"]] = relationship(
        "BRSRQuestion", back_populates="indicator", cascade="all, delete-orphan"
    )


class BRSRQuestion(Base, UUIDMixin, TimestampMixin):
    """
    The specific question or metric required for reporting.
    """

    __tablename__ = "brsr_questions"

    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_type: Mapped[QuestionResponseType] = mapped_column(
        Enum(QuestionResponseType, name="question_response_type"),
        default=QuestionResponseType.NUMBER,
        nullable=False,
    )
    unit_of_measurement: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    indicator_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("brsr_indicators.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    indicator: Mapped["BRSRIndicator"] = relationship(
        "BRSRIndicator", back_populates="questions"
    )
