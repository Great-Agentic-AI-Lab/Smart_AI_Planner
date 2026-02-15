"""
User Preferences Model
Stores user settings for celebrations, notifications, and analytics.
"""
from sqlalchemy import Column, Integer, String, Boolean, JSON, ForeignKey, Time
from sqlalchemy.orm import relationship
from datetime import time

from app.database import Base


class UserPreferences(Base):
    """
    User preferences and settings.
    
    Includes:
    - Festival countries (up to 4)
    - Notification settings
    - Celebration preferences
    - Analytics opt-in
    """
    
    __tablename__ = "user_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Celebration Settings
    festival_countries = Column(JSON, default=list)  # ["India", "USA", "UK", "Canada"]
    auto_send_festival_wishes = Column(Boolean, default=True)
    auto_send_birthday_wishes = Column(Boolean, default=True)
    
    # Notification Settings
    enable_task_reminders = Column(Boolean, default=True)
    enable_daily_digest = Column(Boolean, default=True)
    daily_digest_time = Column(Time, default=time(9, 0))  # 9:00 AM
    reminder_hours_before = Column(JSON, default=list)  # [2, 24] hours before
    
    # Analytics Settings
    enable_weekly_report = Column(Boolean, default=True)
    weekly_report_day = Column(Integer, default=0)  # 0=Monday, 6=Sunday
    
    # Timezone & Language
    timezone = Column(String(50), default="UTC")
    language = Column(String(10), default="en")
    
    # Relationship
    user = relationship("User", back_populates="preferences")
    
    def __repr__(self):
        return f"<UserPreferences(user_id={self.user_id}, countries={self.festival_countries})>"
