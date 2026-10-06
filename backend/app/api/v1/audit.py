"""
Audit Log endpoints for listing and filtering system audit records.
"""

from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import PERM_READ, require_permissions
from backend.app.api.v1.schemas import AuditLogResponse
from backend.app.db.database import get_db
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.user import User

router = APIRouter()


@router.get("", response_model=List[AuditLogResponse])
@router.get("/", response_model=List[AuditLogResponse], include_in_schema=False)
def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    entity_id: Optional[uuid.UUID] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return a list of audit logs ordered by creation timestamp descending."""
    query = db.query(AuditLog)

    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)

    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()

