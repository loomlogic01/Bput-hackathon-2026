"""
Main FastAPI application module.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.v1 import api_router
from backend.app.core.config import settings

app = FastAPI(title="ESG/BRSR Platform API", version="1.0.0")

# Allow the configured front-end origins (e.g. the Vite dev server) to call the
# API from the browser. Origins come from settings.CORS_ORIGINS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def root():
    return {"message": "ESG/BRSR API is running"}
