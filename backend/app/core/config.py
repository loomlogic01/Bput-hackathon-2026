"""
Configuration module for the ESG/BRSR backend.

This file defines a `Settings` class (subclass of `pydantic_settings.BaseSettings`) that
holds all configurable values such as the PostgreSQL connection string, JWT
secret, token expiration, and CORS origins.  The class reads environment variables
automatically and also supports a `.env` file in the project root, which is
convenient for local development.

Why we need it
----------------
* Centralises all configuration so the rest of the code base can simply
  `from backend.app.core.config import settings`.
* Makes it easy to change values without touching code – just edit the `.env`
  file or set environment variables in Docker.
* Provides type‑checking and default values, helping beginners avoid common
  mistakes.

How it connects
----------------
* `backend/app/db/database.py` (to be created) will import `settings` to obtain
  `DATABASE_URL` when creating the SQLAlchemy engine.
* Any future module (auth, file storage, etc.) can also import `settings`
  for the values it needs.
"""

from __future__ import annotations

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for the MVP.

    Values are loaded from environment variables. A `.env` file in the project
    root will be read automatically during local development.
    """

    # Core infrastructure settings
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/esg_brsr"

    # Required - no default. Supplied via the environment or a local .env file
    # (which is git-ignored). A weak or hard-coded fallback would let anyone
    # forge tokens, so the app refuses to start without a real secret.
    JWT_SECRET_KEY: str

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Simple upload directory placeholder (actual handling will be added later)
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MiB

    # CORS configuration – only the local development origin is allowed
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # Pydantic v2 style configuration
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Resolve forward references (required when List is used)
Settings.model_rebuild()

# A single, reusable Settings instance that the rest of the code imports.
settings = Settings()
