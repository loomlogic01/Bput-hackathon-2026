"""
API router v1 registration.
"""

from fastapi import APIRouter

from backend.app.api.v1.auth import router as auth_router
from backend.app.api.v1.brsr import router as brsr_router
from backend.app.api.v1.evidence import router as evidence_router
from backend.app.api.v1.projects import router as projects_router
from backend.app.api.v1.submissions import router as submissions_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(brsr_router, prefix="/brsr", tags=["brsr"])
api_router.include_router(projects_router, prefix="/projects", tags=["projects"])
api_router.include_router(submissions_router, prefix="/submissions", tags=["submissions"])
api_router.include_router(evidence_router, prefix="/submissions", tags=["evidence"])
