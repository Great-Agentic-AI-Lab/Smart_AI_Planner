"""
Birthday Model 
Tracks birthdays with personalized wish language for each person.
"""
from sqlalchemy import Column, Integer, String, Date, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class Birthday(Base):
    """
    Birthday tracking with per-person language preferences.
    
    New: Each person can have wishes in their preferred language!
    """
    
    __tablename__ = "birthdays"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Person Details
    person_name = Column(String(100), nullable=False)
    relation = Column(String(50), nullable=False)  # friend, family, wife, colleague, etc.
    birthday_date = Column(Date, nullable=False)  # MM-DD (year-agnostic)
    
    # Optional Details
    age = Column(Integer, nullable=True)
    interests = Column(JSON, default=list)  # ["cooking", "travel", "music"]
    
    # NEW: Wish Language (can be different from user's default!)
    wish_language = Column(String(10), default="en")  # en, hi, mr, es, fr, de, ar, zh, ja
    
    # Reminder Settings
    reminder_days_before = Column(Integer, default=1)
    send_on_day = Column(Boolean, default=True)
    
    # Relationship
    user = relationship("User", back_populates="birthdays")
    
    def is_birthday_today(self) -> bool:
        """Check if today is this person's birthday."""
        today = datetime.utcnow().date()
        return (
            self.birthday_date.month == today.month and
            self.birthday_date.day == today.day
        )
    
    def is_birthday_soon(self, days: int = 7) -> bool:
        """Check if birthday is within next N days."""
        today = datetime.utcnow().date()
        this_year_birthday = self.birthday_date.replace(year=today.year)
        
        if this_year_birthday < today:
            this_year_birthday = this_year_birthday.replace(year=today.year + 1)
        
        days_until = (this_year_birthday - today).days
        return 0 <= days_until <= days
    
    def days_until_birthday(self) -> int:
        """Get number of days until next birthday."""
        today = datetime.utcnow().date()
        this_year_birthday = self.birthday_date.replace(year=today.year)
        
        if this_year_birthday < today:
            this_year_birthday = this_year_birthday.replace(year=today.year + 1)
        
        return (this_year_birthday - today).days
    
    def get_language_name(self) -> str:
        """Get human-readable language name."""
        languages = {
            'en': 'English',
            'hi': 'Hindi',
            'mr': 'Marathi',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'ar': 'Arabic',
            'zh': 'Chinese',
            'ja': 'Japanese'
        }
        return languages.get(self.wish_language, 'English')
    
    def __repr__(self):
        return f"<Birthday(person={self.person_name}, relation={self.relation}, date={self.birthday_date}, lang={self.wish_language})>"
