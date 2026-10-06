"""
Audit logging service for non-destructive event recording across the platform.
"""

import logging
from typing import Any, Dict, Optional
import uuid

from sqlalchemy.orm import Session

from backend.app.db.models.audit import AuditLog
from backend.app.db.models.user import User

logger = logging.getLogger(__name__)


def create_audit_log(
    db: Session,
    user: Optional[User],
    action: str,
    entity_type: str,
    entity_id: Optional[uuid.UUID] = None,
    description: Optional[str] = None,
    old_value: Optional[Dict[str, Any]] = None,
    new_value: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> Optional[AuditLog]:
    """Record an audit log entry in a non-destructive manner.

    Failure during audit logging is caught and logged so that primary business
    operations complete uninterrupted.
    """
    try:
        user_id = user.id if user else None

        # Sanitize sensitive fields if present in value dictionaries
        def _sanitize(val: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not isinstance(val, dict):
                return val
            cleaned = {}
            for k, v in val.items():
                k_str = str(k).lower()
                if any(secret in k_str for secret in ("password", "token", "secret", "hash")):
                    cleaned[k] = "******"
                elif isinstance(v, str) and any(secret in v.lower() for secret in ("password", "token", "secret", "hash")):
                    cleaned[k] = "******"
                else:
                    cleaned[k] = v
            return cleaned

        log_entry = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_value=_sanitize(old_value),
            new_value=_sanitize(new_value),
            ip_address=ip_address,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry
    except Exception as exc:
        logger.warning("Non-destructive audit logging failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return None
