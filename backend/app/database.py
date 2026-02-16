"""
Database configuration and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database tables.
    Creates all tables defined in models.
    """
    # Import ALL models to ensure they're registered with SQLAlchemy
    from app.models import (
        User,
        Task,
        Event,
        Birthday,
        UserPreferences,
        PriorityEnum,
        TaskStatusEnum
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully!")
    logger.info(f"   - Users")
    logger.info(f"   - Tasks")
    logger.info(f"   - Events")
    logger.info(f"   - Birthdays")
    logger.info(f"   - User Preferences")
