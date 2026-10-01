"""
User and Role-Based Access Control (RBAC) models:
User, Role, Permission, user_roles (join table), role_permissions (join table)
"""

import enum
import uuid
from typing import List, Optional

from sqlalchemy import Boolean, Column, Enum, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin

# Association table for Many-to-Many relationship between User and Role
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Many-to-Many relationship between Role and Permission
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class SystemRole(str, enum.Enum):
    """
    Standard RBAC roles planned for the ESG/BRSR platform.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    GROUP_ESG_ADMIN = "GROUP_ESG_ADMIN"
    SUBSIDIARY_ESG_MANAGER = "SUBSIDIARY_ESG_MANAGER"
    BUSINESS_UNIT_MANAGER = "BUSINESS_UNIT_MANAGER"
    PROJECT_DATA_ENTRY = "PROJECT_DATA_ENTRY"
    REVIEWER = "REVIEWER"
    APPROVER = "APPROVER"
    AUDITOR = "AUDITOR"


class Permission(Base, UUIDMixin, TimestampMixin):
    """
    Represents an atomic action/privilege in the system (e.g. 'submission:approve').
    """

    __tablename__ = "permissions"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Many-to-many relationship back to Role
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions"
    )


class Role(Base, UUIDMixin, TimestampMixin):
    """
    Represents a group of permissions assigned to users (e.g. 'PROJECT_DATA_ENTRY').
    """

    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Many-to-many relationship to Permission
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles"
    )

    # Many-to-many relationship to User
    users: Mapped[List["User"]] = relationship(
        "User", secondary=user_roles, back_populates="roles"
    )


class User(Base, UUIDMixin, TimestampMixin):
    """
    User model representing platform users with authentication details and RBAC roles.
    """

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Optional foreign keys to scope user access within the organization hierarchy
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    business_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("business_units.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )

    # Many-to-many relationship to Role
    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users"
    )
