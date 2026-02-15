"""
User model for storing user information.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    """Database model representing a user."""

    __tablename__ = "users"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)

    # User info
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)

    # Preferences
    timezone = Column(String, default="UTC")
    notifications_enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)

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
    preferences = relationship(
        "UserPreferences",
        back_populates="user",
        uselist=False
    )
    birthdays = relationship(
        "Birthday",
        back_populates="user"
    )

    def __repr__(self) -> str:
        return (
            f"<User(id={self.id}, telegram_id={self.telegram_id}, "
            f"username={self.username}, email={self.email})>"
        )

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
            "task_count": len(self.tasks) if self.tasks else 0,
            "event_count": len(self.events) if self.events else 0,
        }