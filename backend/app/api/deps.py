"""
API dependencies for database sessions and authentication.
"""

import uuid
from typing import Optional, Set

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.db.database import get_db
from backend.app.db.models.organization import BusinessUnit, Entity, Project
from backend.app.db.models.user import SystemRole, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# Permission names, as seeded by backend/app/db/seed.py.
PERM_READ = "submission:read"
PERM_CREATE = "submission:create"
PERM_UPDATE = "submission:update"
PERM_SUBMIT = "submission:submit"
PERM_REVIEW = "submission:review"
PERM_APPROVE = "submission:approve"


def get_current_user(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
) -> User:
    """
    Dependency to validate the JWT token and return the currently authenticated user.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id_str: str = payload.get("sub")
    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        # If subject was email or invalid UUID
        user = db.query(User).filter_by(email=user_id_str).first()
        if user is None:
            raise credentials_exception
        return user

    user = db.query(User).filter_by(id=user_id).first()
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    return user


# ── Role / permission helpers ──
# These enforce the existing Role -> Permission and
# Organization -> Entity -> BusinessUnit -> Project models. No schema change.

def is_super_admin(user: User) -> bool:
    """SUPER_ADMIN bypasses both permission checks and scope filtering."""
    return any(r.name == SystemRole.SUPER_ADMIN.value for r in user.roles)


def get_permissions(user: User) -> Set[str]:
    """All permission names granted through the user's roles."""
    return {p.name for role in user.roles for p in role.permissions}


def has_permission(user: User, permission: str) -> bool:
    """True if the user holds the permission, or is a SUPER_ADMIN."""
    if is_super_admin(user):
        return True
    return permission in get_permissions(user)


def require_permissions(*permissions: str):
    """Dependency factory that enforces one or more permissions.

    Raises 403 when the authenticated user lacks any of them. Because this
    wraps get_current_user, an absent or invalid token still yields 401.
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        missing = [p for p in permissions if not has_permission(current_user, p)]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Missing required permission(s): " + ", ".join(missing),
            )
        return current_user

    return dependency


# ── Organisation / project scope helpers ──

def accessible_project_ids(db: Session, user: User) -> Optional[Set[uuid.UUID]]:
    """Project ids the user may reach.

    Returns ``None`` to mean "unrestricted" (SUPER_ADMIN). Otherwise the set is
    the union of the projects reachable from the hierarchy levels the user is
    assigned to. A user with no assignment gets an empty set.
    """
    if is_super_admin(user):
        return None

    ids: Set[uuid.UUID] = set()

    if user.project_id:
        ids.add(user.project_id)

    if user.business_unit_id:
        ids.update(
            p.id
            for p in db.query(Project).filter_by(business_unit_id=user.business_unit_id)
        )

    if user.entity_id:
        ids.update(
            p.id
            for p in db.query(Project)
            .join(BusinessUnit, Project.business_unit_id == BusinessUnit.id)
            .filter(BusinessUnit.entity_id == user.entity_id)
        )

    if user.organization_id:
        ids.update(
            p.id
            for p in db.query(Project)
            .join(BusinessUnit, Project.business_unit_id == BusinessUnit.id)
            .join(Entity, BusinessUnit.entity_id == Entity.id)
            .filter(Entity.organization_id == user.organization_id)
        )

    return ids


def accessible_organization_ids(db: Session, user: User) -> Optional[Set[uuid.UUID]]:
    """Organization ids the user may reach, or ``None`` for unrestricted."""
    if is_super_admin(user):
        return None
    if user.organization_id:
        return {user.organization_id}
    if user.entity_id:
        return {
            e.organization_id
            for e in db.query(Entity).filter_by(id=user.entity_id)
            if e.organization_id
        }
    if user.business_unit_id:
        bu = db.query(BusinessUnit).filter_by(id=user.business_unit_id).first()
        if bu is None:
            return set()
        ent = db.query(Entity).filter_by(id=bu.entity_id).first()
        return {ent.organization_id} if ent and ent.organization_id else set()
    return set()


def can_access_project(db: Session, user: User, project_id: uuid.UUID) -> bool:
    """True if the user may touch the given project."""
    ids = accessible_project_ids(db, user)
    return ids is None or project_id in ids


def ensure_project_access(
    db: Session, user: User, project_id: uuid.UUID
) -> None:
    """Raise 403 unless the user may touch the given project."""
    if not can_access_project(db, user, project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this project.",
        )
