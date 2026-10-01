"""
Audit model for tracking important system actions across the ESG/BRSR platform.
"""

from typing import Any, Dict, Optional
import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin


class AuditLog(Base, UUIDMixin, TimestampMixin):
    """
    AuditLog model to maintain immutable logs of security, data entry, workflow transitions,
    and administrative actions across the platform.
    """

    __tablename__ = "audit_logs"

    # Optional foreign key to users.id; SET NULL if user is deleted
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Action performed, e.g. USER_LOGIN, SUBMISSION_STATUS_CHANGED, VALUE_UPDATED
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Affected entity type, e.g. Submission, User, Project
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Optional UUID of the affected entity
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Historical state before change
    old_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # New state after change
    new_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)

    # Human-readable explanation or additional context
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Client IP address
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Relationship to user
    user: Mapped[Optional["User"]] = relationship("User", backref="audit_logs")  # type: ignore # noqa: F821

    def __repr__(self) -> str:
        return f"<AuditLog(action='{self.action}', entity_type='{self.entity_type}', entity_id='{self.entity_id}', user_id='{self.user_id}')>"
