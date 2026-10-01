"""
Organization hierarchy models representing:
Organization (Group) -> Entity (Subsidiary) -> BusinessUnit (Division) -> Project (Site)
"""

import uuid
from typing import List, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin


class Organization(Base, UUIDMixin, TimestampMixin):
    """
    Top-level parent organization or conglomerate (e.g., MEIL Group).
    """

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # 1-to-Many relationship to child Entities
    entities: Mapped[List["Entity"]] = relationship(
        "Entity", back_populates="organization", cascade="all, delete-orphan"
    )


class Entity(Base, UUIDMixin, TimestampMixin):
    """
    Subsidiary or legal entity under an Organization (e.g., MEIL Energy).
    """

    __tablename__ = "entities"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="entities"
    )
    business_units: Mapped[List["BusinessUnit"]] = relationship(
        "BusinessUnit", back_populates="entity", cascade="all, delete-orphan"
    )


class BusinessUnit(Base, UUIDMixin, TimestampMixin):
    """
    Department or operational division within a Subsidiary (e.g., Solar Division).
    """

    __tablename__ = "business_units"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    entity: Mapped["Entity"] = relationship("Entity", back_populates="business_units")
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="business_unit", cascade="all, delete-orphan"
    )


class Project(Base, UUIDMixin, TimestampMixin):
    """
    Specific operational site or facility under a Business Unit (e.g., Kurnool Solar Site).
    """

    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), index=True, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business_units.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    business_unit: Mapped["BusinessUnit"] = relationship(
        "BusinessUnit", back_populates="projects"
    )
