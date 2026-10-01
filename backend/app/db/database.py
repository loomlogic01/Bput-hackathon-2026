"""
Database setup and session management for the ESG/BRSR backend.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import our settings from the config file we just created
from backend.app.core.config import settings

# 1. Create the SQLAlchemy Engine
# This establishes the core connection pool to PostgreSQL.
engine = create_engine(settings.DATABASE_URL)

# 2. Create the Session factory
# autocommit=False and autoflush=False are standard for SQLAlchemy 2.x
# to prevent accidental saves before we explicitly call db.commit()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 3. Dependency to get a database session
def get_db():
    """
    Creates a new database session for a single request and closes it when done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
