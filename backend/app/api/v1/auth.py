"""
Authentication API endpoints: /login and /me.
"""

from typing import Any, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.security import create_access_token, verify_password
from backend.app.db.database import get_db
from backend.app.db.models.user import User

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    organization_id: Optional[uuid.UUID] = None
    entity_id: Optional[uuid.UUID] = None
    business_unit_id: Optional[uuid.UUID] = None
    project_id: Optional[uuid.UUID] = None

    class Config:
        from_attributes = True


@router.post("/login", response_model=TokenResponse)
def login(
    request: LoginRequest, db: Session = Depends(get_db)
) -> Any:
    """
    Authenticate user with email and password, returning a JWT access token.
    """
    user = db.query(User).filter_by(email=request.email).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> Any:
    """
    Return currently authenticated user information.
    """
    return current_user
