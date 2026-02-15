"""
Database configuration and session management.
Uses SQLAlchemy with PostgreSQL (sync mode for simplicity).
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Create database engine (SYNC)
engine = create_engine(
    settings.database_url,  # Use regular DATABASE_URL
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.debug
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Use with FastAPI Depends().
    
    Usage:
        @app.get("/items")
        def get_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
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
    from app.models import task, event, user  # Import all models
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created successfully!")


def drop_db() -> None:
    """
    Drop all database tables.
    Use with caution - deletes all data!
    """
    Base.metadata.drop_all(bind=engine)
    logger.warning(" All database tables dropped!")
