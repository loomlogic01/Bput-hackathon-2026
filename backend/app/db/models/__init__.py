"""
Models package for the ESG/BRSR reporting platform.
Exposes Base and all database models so they are registered in Base.metadata.
"""

from backend.app.db.models.base import Base, TimestampMixin, UUIDMixin
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.brsr import (
    BRSRFramework,
    BRSRIndicator,
    BRSRPrinciple,
    BRSRQuestion,
    BRSRSection,
    IndicatorType,
    QuestionResponseType,
)
from backend.app.db.models.organization import (
    BusinessUnit,
    Entity,
    Organization,
    Project,
)
from backend.app.db.models.reporting import (
    ReportingBoundary,
    ReportingPeriod,
)
from backend.app.db.models.submission import (
    ApprovalWorkflow,
    Evidence,
    Submission,
    SubmissionStatus,
    SubmissionValue,
)
from backend.app.db.models.user import (
    Permission,
    Role,
    SystemRole,
    User,
    role_permissions,
    user_roles,
)

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "Organization",
    "Entity",
    "BusinessUnit",
    "Project",
    "User",
    "Role",
    "Permission",
    "SystemRole",
    "user_roles",
    "role_permissions",
    "ReportingPeriod",
    "ReportingBoundary",
    "BRSRFramework",
    "BRSRSection",
    "BRSRPrinciple",
    "BRSRIndicator",
    "BRSRQuestion",
    "IndicatorType",
    "QuestionResponseType",
    "SubmissionStatus",
    "Submission",
    "SubmissionValue",
    "Evidence",
    "ApprovalWorkflow",
    "AuditLog",
]
