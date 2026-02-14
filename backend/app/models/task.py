"""
Task model for storing user tasks with priority and effort estimation.
"""

from datetime import datetime
from typing import Optional, List
import enum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum, Float, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship
from app.database import Base


class PriorityEnum(str, enum.Enum):
    """Task priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatusEnum(str, enum.Enum):
    """Task completion status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(Base):
    """Task model with AI-powered prioritization."""

    __tablename__ = "tasks"

    # Primary key
    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Task details
    title: str = Column(String(255), nullable=False)
    description: Optional[str] = Column(Text, nullable=True)

    # Priority & effort (AI-generated)
    priority: PriorityEnum = Column(Enum(PriorityEnum), default=PriorityEnum.MEDIUM)
    priority_score: float = Column(Float, default=50.0)  # AI score 0-100
    estimated_effort_minutes: Optional[int] = Column(Integer, nullable=True)
    actual_effort_minutes: Optional[int] = Column(Integer, nullable=True)

    # Deadlines
    due_date: Optional[datetime] = Column(DateTime, nullable=True)

    # Status
    status: TaskStatusEnum = Column(Enum(TaskStatusEnum), default=TaskStatusEnum.PENDING)
    completed_at: Optional[datetime] = Column(DateTime, nullable=True)

    # Metadata
    tags: Optional[str] = Column(String, nullable=True)  # Comma-separated
    context: Optional[str] = Column(Text, nullable=True)  # AI context

    # Tracking
    postponed_count: int = Column(Integer, default=0)
    is_recurring: bool = Column(Boolean, default=False)

    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="tasks")

    def __repr__(self) -> str:
        return (
            f"<Task(id={self.id}, title={self.title}, "
            f"priority={self.priority}, status={self.status})>"
        )

    def to_dict(self) -> dict:
        """Convert task instance to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value if self.priority else None,
            "priority_score": self.priority_score,
            "estimated_effort_minutes": self.estimated_effort_minutes,
            "actual_effort_minutes": self.actual_effort_minutes,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "status": self.status.value if self.status else None,
            "tags": self.tags.split(",") if self.tags else [],
            "context": self.context,
            "postponed_count": self.postponed_count,
            "is_recurring": self.is_recurring,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    # --------------------------
    # Helper methods
    # --------------------------
    def is_overdue(self) -> bool:
        """Check if task is past due date."""
        return bool(self.due_date and datetime.utcnow() > self.due_date)

    def remaining_minutes(self) -> Optional[int]:
        """Return estimated remaining minutes for the task."""
        if self.estimated_effort_minutes and self.actual_effort_minutes:
            return max(self.estimated_effort_minutes - self.actual_effort_minutes, 0)
        return self.estimated_effort_minutes
