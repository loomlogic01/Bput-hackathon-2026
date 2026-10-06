"""
Evidence attachment endpoints for submissions.

Files are streamed to disk under ``settings.UPLOAD_DIR``. Only the row is
recorded against a submission; download and delete are not part of this MVP.
"""

import os
import re
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from backend.app.api.deps import PERM_READ, PERM_UPDATE, require_permissions
from backend.app.api.v1.schemas import EvidenceResponse
from backend.app.api.v1.submissions import (
    EDITABLE_STATUSES,
    load_scoped_submission,
)
from backend.app.core.config import settings
from backend.app.db.database import get_db
from backend.app.db.models.submission import Evidence, SubmissionValue
from backend.app.db.models.user import User
from backend.app.services.audit import create_audit_log

router = APIRouter()

# Streamed in 64 KiB chunks so an oversized upload is never fully buffered.
CHUNK_SIZE = 64 * 1024

# Only a short, plain extension is carried over to the stored filename.
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,10}$")


class _UploadTooLarge(Exception):
    """Internal signal so the partially written file can be removed."""


def _upload_root() -> Path:
    return Path(settings.UPLOAD_DIR).resolve()


def _stored_extension(file_name: Optional[str]) -> str:
    """A conservative suffix, or '' - never a path fragment from the client."""
    suffix = Path(file_name or "").suffix
    return suffix if _SAFE_SUFFIX.match(suffix) else ""


@router.get(
    "/{submission_id}/evidence",
    response_model=List[EvidenceResponse],
)
def list_submission_evidence(
    submission_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_READ)),
):
    """Return the evidence attached to a submission, oldest first."""
    load_scoped_submission(submission_id, db, current_user)
    return (
        db.query(Evidence)
        .filter_by(submission_id=submission_id)
        .order_by(Evidence.created_at)
        .all()
    )


@router.post(
    "/{submission_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_submission_evidence(
    submission_id: uuid.UUID,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    submission_value_id: Optional[uuid.UUID] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions(PERM_UPDATE)),
):
    """Attach an uploaded file as evidence for a submission."""
    submission = load_scoped_submission(submission_id, db, current_user)

    if submission.status not in EDITABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Cannot add evidence to a submission in "
                f"{submission.status.value} status. Only DRAFT or "
                f"CORRECTION_REQUIRED submissions can be edited."
            ),
        )

    # The optional link must point at an answer inside this same submission.
    if submission_value_id is not None:
        value = (
            db.query(SubmissionValue).filter_by(id=submission_value_id).first()
        )
        if value is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Submission value not found",
            )
        if value.submission_id != submission.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That submission value belongs to a different submission.",
            )

    root = _upload_root()
    dest_dir = root / str(submission.id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # The stored name is generated, so a hostile filename cannot influence the
    # path that gets written to.
    stored_name = f"{uuid.uuid4().hex}{_stored_extension(file.filename)}"
    dest = (dest_dir / stored_name).resolve()
    if not str(dest).startswith(str(root) + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid upload path.",
        )

    written = 0
    try:
        with dest.open("wb") as out:
            while True:
                chunk = file.file.read(CHUNK_SIZE)
                if not chunk:
                    break
                written += len(chunk)
                if written > settings.MAX_UPLOAD_SIZE:
                    raise _UploadTooLarge()
                out.write(chunk)
    except _UploadTooLarge:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"File exceeds the maximum upload size of "
                f"{settings.MAX_UPLOAD_SIZE} bytes."
            ),
        )
    except OSError:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not store the uploaded file.",
        )
    finally:
        file.file.close()

    if written == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    row = Evidence(
        submission_id=submission.id,
        submission_value_id=submission_value_id,
        uploaded_by_id=current_user.id,
        file_name=file.filename or stored_name,
        # Relative to UPLOAD_DIR; no absolute path is ever persisted.
        storage_path=f"{submission.id}/{stored_name}",
        content_type=file.content_type,
        file_size_bytes=written,
        description=description,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    create_audit_log(
        db=db,
        user=current_user,
        action="EVIDENCE_UPLOADED",
        entity_type="Evidence",
        entity_id=row.id,
        description=f"Uploaded evidence file '{row.file_name}' for submission {submission_id}",
        new_value={
            "file_name": row.file_name,
            "file_size_bytes": row.file_size_bytes,
        },
    )
    return row