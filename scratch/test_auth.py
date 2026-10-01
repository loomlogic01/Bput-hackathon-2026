"""
Verification script for backend authentication foundation.
"""

import sys
import uuid
from fastapi.testclient import TestClient

from backend.app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from backend.app.db.database import SessionLocal
from backend.app.db.models.user import User
from backend.app.main import app

def test_security_utils():
    print("--- 1. Testing Security Utilities ---")
    password = "SecretPassword123!"
    hashed = get_password_hash(password)
    assert verify_password(password, hashed), "Password verification failed!"
    assert not verify_password("WrongPassword", hashed), "Invalid password check failed!"
    print("[PASS] Password hashing & verification working")

    test_sub = str(uuid.uuid4())
    token = create_access_token(test_sub)
    payload = decode_access_token(token)
    assert payload is not None, "Token decoding failed!"
    assert payload.get("sub") == test_sub, "Token subject mismatch!"
    print("[PASS] JWT creation & decoding working")

def test_auth_endpoints():
    print("\n--- 2. Testing Auth API Endpoints ---")
    client = TestClient(app)

    # Prepare demo user in DB
    db = SessionLocal()
    test_email = "test.user@meil.in"
    test_password = "Password123"

    try:
        user = db.query(User).filter_by(email=test_email).first()
        if not user:
            user = User(
                email=test_email,
                hashed_password=get_password_hash(test_password),
                full_name="Test User",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # A. Test invalid credentials (401)
        resp_invalid = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": "WrongPassword"},
        )
        assert resp_invalid.status_code == 401, f"Expected 401, got {resp_invalid.status_code}"
        print("[PASS] Invalid credentials returned 401 Unauthorized")

        # B. Test valid login (200 & JWT)
        resp_valid = client.post(
            "/api/v1/auth/login",
            json={"email": test_email, "password": test_password},
        )
        assert resp_valid.status_code == 200, f"Expected 200, got {resp_valid.status_code}"
        data = resp_valid.json()
        assert "access_token" in data, "Token missing in login response!"
        token = data["access_token"]
        print("[PASS] Valid login returned 200 and access_token")

        # C. Test /me without token (401)
        resp_me_unauth = client.get("/api/v1/auth/me")
        assert resp_me_unauth.status_code == 401, f"Expected 401, got {resp_me_unauth.status_code}"
        print("[PASS] /auth/me without token returned 401 Unauthorized")

        # D. Test /me with valid token (200)
        headers = {"Authorization": f"Bearer {token}"}
        resp_me = client.get("/api/v1/auth/me", headers=headers)
        assert resp_me.status_code == 200, f"Expected 200, got {resp_me.status_code}"
        me_data = resp_me.json()
        assert me_data["email"] == test_email, "User email mismatch in /me response!"
        print("[PASS] /auth/me with valid token returned 200 and user details")

    finally:
        db.close()

if __name__ == "__main__":
    test_security_utils()
    test_auth_endpoints()
    print("\n[SUCCESS] All backend authentication tests passed!")
