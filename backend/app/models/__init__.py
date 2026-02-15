"""
Models package initialization.

Imports all database models for easy access throughout the application.
"""

from app.models.user import User
from app.models.task import Task, PriorityEnum, TaskStatusEnum
from app.models.event import Event
from app.models.birthday_model import Birthday
from app.models.user_preferences_model import UserPreferences 

__all__ = [
    "User",
    "Task",
    "PriorityEnum",
    "TaskStatusEnum",
    "Event",
    "Birthday",
    "UserPreferences",
]
