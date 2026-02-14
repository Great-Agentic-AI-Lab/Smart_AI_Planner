"""
User model for storing user information.
"""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """Database model representing a user."""

    __tablename__ = "users"

    # Primary key
    id: int = Column(Integer, primary_key=True, index=True)
    telegram_id: int = Column(Integer, unique=True, index=True, nullable=False)

    # User info
    username: Optional[str] = Column(String, nullable=True)
    first_name: Optional[str] = Column(String, nullable=True)
    last_name: Optional[str] = Column(String, nullable=True)
    email: Optional[str] = Column(String, unique=True, index=True, nullable=True)

    # Preferences
    timezone: str = Column(String, default="UTC")
    notifications_enabled: bool = Column(Boolean, default=True)

    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active: datetime = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tasks = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    events = relationship(
        "Event",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, telegram_id={self.telegram_id}, "
            f"username={self.username}, email={self.email})>"
        )

    # --------------------------
    # Helper methods
    # --------------------------
    def full_name(self) -> str:
        """Return user's full name if available, else username."""
        if self.first_name or self.last_name:
            return f"{self.first_name or ''} {self.last_name or ''}".strip()
        return self.username or f"User-{self.id}"

    def to_dict(self) -> dict:
        """Convert user instance to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "telegram_id": self.telegram_id,
            "username": self.username,
            "full_name": self.full_name(),
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "timezone": self.timezone,
            "notifications_enabled": self.notifications_enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "task_count": len(self.tasks),
            "event_count": len(self.events),
        }
