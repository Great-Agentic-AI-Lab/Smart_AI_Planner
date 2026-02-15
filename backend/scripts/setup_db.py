"""
Database initialization and setup script.
Run this to create tables and seed initial data.
"""
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, SessionLocal
from app.models import User
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_default_user():
    """Create a default user for testing."""
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.telegram_id == 123456789).first()
        
        if existing_user:
            logger.info("Default user already exists")
            return
        
        # Create default user
        default_user = User(
            telegram_id=123456789,
            username="test_user",
            first_name="Test",
            last_name="User",
            email="test@example.com",
            timezone="UTC",
            notifications_enabled=True,
            created_at=datetime.utcnow(),
            last_active=datetime.utcnow()
        )
        
        db.add(default_user)
        db.commit()
        logger.info(" Default user created successfully!")
        
    except Exception as e:
        logger.error(f" Error creating default user: {e}")
        db.rollback()
    finally:
        db.close()


def main():
    """Main setup function."""
    logger.info(" Initializing database...")
    
    try:
        # Create tables
        init_db()
        
        # Create default user
        create_default_user()
        
        logger.info(" Database setup completed successfully!")
        logger.info("You can now run: uvicorn app.main:app --reload")
        
    except Exception as e:
        logger.error(f" Database setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
