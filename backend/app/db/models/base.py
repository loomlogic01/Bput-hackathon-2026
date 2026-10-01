"""
Base module providing the declarative base and common mixins for all database models.
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    The master blueprint. Every database model will inherit from this class.
    SQLAlchemy 2.x uses this new DeclarativeBase class approach.
    """
    pass


class UUIDMixin:
    """
    Provides a universally unique identifier (UUID) as the primary key.
    Using Mapped and mapped_column is the standard for SQLAlchemy 2.x.
    """
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, 
        default=uuid.uuid4,
        sort_order=-100  # Ensures the ID column appears first in the table
    )


class TimestampMixin:
    """
    Automatically adds and manages 'created_at' and 'updated_at' timestamps.
    """
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        sort_order=9998  # Ensures timestamps appear at the end of the table
    )
    
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(),
        onupdate=func.now(),
        sort_order=9999
    )
