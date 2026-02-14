"""
Event model for calendar events (meetings, deadlines, appointments).
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class Event(Base):
    """Database model for calendar events."""

    __tablename__ = "events"

    # Primary key
    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Event details
    title: str = Column(String(255), nullable=False)
    description: Optional[str] = Column(Text, nullable=True)
    location: Optional[str] = Column(String(255), nullable=True)

    # Timing
    start_time: datetime = Column(DateTime, nullable=False)
    end_time: datetime = Column(DateTime, nullable=False)
    all_day: bool = Column(Boolean, default=False)

    # Reminders
    reminder_minutes_before: int = Column(Integer, default=30)

    # Special types
    is_birthday: bool = Column(Boolean, default=False)
    is_festival: bool = Column(Boolean, default=False)
    festival_name: Optional[str] = Column(String(100), nullable=True)

    # Recurrence
    is_recurring: bool = Column(Boolean, default=False)
    recurrence_rule: Optional[str] = Column(String, nullable=True)

    # Integration
    google_calendar_id: Optional[str] = Column(String, nullable=True)

    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="events")

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title={self.title}, start_time={self.start_time})>"

    def to_dict(self) -> dict:
        """Convert event instance to dictionary for JSON serialization."""
        fmt = lambda dt: dt.isoformat() if dt else None
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "start_time": fmt(self.start_time),
            "end_time": fmt(self.end_time),
            "all_day": self.all_day,
            "reminder_minutes_before": self.reminder_minutes_before,
            "is_birthday": self.is_birthday,
            "is_festival": self.is_festival,
            "festival_name": self.festival_name,
            "is_recurring": self.is_recurring,
            "recurrence_rule": self.recurrence_rule,
            "google_calendar_id": self.google_calendar_id,
            "created_at": fmt(self.created_at),
            "updated_at": fmt(self.updated_at),
        }

    def duration_minutes(self) -> int:
        """Return event duration in minutes."""
        return int((self.end_time - self.start_time).total_seconds() / 60)

    def is_upcoming(self) -> bool:
        """Return True if event is in the future."""
        return datetime.utcnow() < self.start_time
