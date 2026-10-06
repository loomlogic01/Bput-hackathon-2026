"""
Phase 4B focused unit tests for Audit Log functionality.

Tests:
1. Audit helper creates a record (non-destructive execution).
2. Audit endpoint authentication and listing access.
3. Login creates USER_LOGIN audit log.
4. Submission value update creates VALUE_UPDATED audit log.
5. Evidence upload creates EVIDENCE_UPLOADED audit log.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token, get_password_hash
from backend.app.db.database import SessionLocal
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.brsr import BRSRQuestion
from backend.app.db.models.organization import Project
from backend.app.db.models.reporting import ReportingPeriod
from backend.app.db.models.submission import Submission, SubmissionStatus
from backend.app.db.models.user import Permission, Role, User
from backend.app.main import app
from backend.app.services.audit import create_audit_log

client = TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db):
    user = db.query(User).filter_by(email="audit.test@meil.in").first()
    project = db.query(Project).first()
    if not user:
        perm = db.query(Permission).filter_by(name="submission:read").first()
        if not perm:
            perm = Permission(name="submission:read", description="Read submissions")
            db.add(perm)
            db.flush()
        perm_update = db.query(Permission).filter_by(name="submission:update").first()
        if not perm_update:
            perm_update = Permission(name="submission:update", description="Update submissions")
            db.add(perm_update)
            db.flush()

        role = db.query(Role).filter_by(name="AUDIT_TEST_ROLE").first()
        if not role:
            role = Role(name="AUDIT_TEST_ROLE", description="Test Role")
            role.permissions.extend([perm, perm_update])
            db.add(role)
            db.flush()

        user = User(
            email="audit.test@meil.in",
            hashed_password=get_password_hash("Password123"),
            full_name="Audit Test User",
            is_active=True,
            project_id=project.id if project else None,
        )
        user.roles.append(role)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif project and user.project_id != project.id:
        user.project_id = project.id
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {token}"}


def test_audit_helper_creates_record(db, test_user):
    """Test 1: create_audit_log service helper successfully records an entry."""
    entry = create_audit_log(
        db=db,
        user=test_user,
        action="TEST_ACTION",
        entity_type="TestEntity",
        entity_id=test_user.id,
        description="UnitTest audit entry",
        old_value={"password": "secret_password_123"},
        new_value={"password": "updated_value"},
    )
    assert entry is not None
    assert entry.action == "TEST_ACTION"
    assert entry.user_id == test_user.id
    # Ensure sensitive keyword is sanitized
    assert entry.old_value["password"] == "******"


def test_audit_endpoint_access(db, auth_headers):
    """Test 2: GET /api/v1/audit-logs returns audit logs with auth."""
    # Unauthenticated request should fail with 401
    res = client.get("/api/v1/audit-logs")
    assert res.status_code == 401

    # Authenticated request should return 200
    res = client.get("/api/v1/audit-logs", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_login_creates_user_login_audit(db, test_user):
    """Test 3: Login endpoint creates a USER_LOGIN audit log entry."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": test_user.email, "password": "Password123"},
    )
    assert res.status_code == 200

    db.expire_all()
    logs = db.query(AuditLog).filter_by(action="USER_LOGIN", user_id=test_user.id).all()
    assert len(logs) > 0


def test_value_update_creates_value_updated_audit(db, auth_headers, test_user):
    """Test 4: Submission value upsert creates a VALUE_UPDATED audit log entry."""
    period = db.query(ReportingPeriod).first()
    question = db.query(BRSRQuestion).first()
    project = db.query(Project).first()
    if not period or not question or not project:
        pytest.skip("Database missing seeded reporting period, project or question")

    sub = Submission(
        project_id=project.id,
        reporting_period_id=period.id,
        framework_id=question.indicator.section.framework_id,
        status=SubmissionStatus.DRAFT,
        created_by_id=test_user.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    payload = {
        "question_id": str(question.id),
        "value_numeric": 99.5,
        "value_text": "99.5",
    }
    res = client.post(
        f"/api/v1/submissions/{sub.id}/values",
        json=payload,
        headers=auth_headers,
    )
    assert res.status_code == 201

    db.expire_all()
    logs = db.query(AuditLog).filter_by(action="VALUE_UPDATED", user_id=test_user.id).all()
    assert len(logs) > 0


def test_evidence_upload_creates_evidence_uploaded_audit(db, auth_headers, test_user):
    """Test 5: Evidence file upload creates an EVIDENCE_UPLOADED audit log entry."""
    period = db.query(ReportingPeriod).first()
    question = db.query(BRSRQuestion).first()
    project = db.query(Project).first()
    if not period or not question or not project:
        pytest.skip("Database missing seeded reporting period, project or question")

    sub = Submission(
        project_id=project.id,
        reporting_period_id=period.id,
        framework_id=question.indicator.section.framework_id,
        status=SubmissionStatus.DRAFT,
        created_by_id=test_user.id,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    files = {"file": ("test_audit_proof.pdf", b"Dummy proof content", "application/pdf")}
    res = client.post(
        f"/api/v1/submissions/{sub.id}/evidence",
        files=files,
        headers=auth_headers,
    )
    assert res.status_code == 201

    db.expire_all()
    logs = db.query(AuditLog).filter_by(action="EVIDENCE_UPLOADED", user_id=test_user.id).all()
    assert len(logs) > 0

