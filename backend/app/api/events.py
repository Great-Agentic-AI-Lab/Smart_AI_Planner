"""
Event Management API Endpoints
Provides CRUD operations for calendar events.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import Event

router = APIRouter()


# -----------------------------
# Pydantic Schemas
# -----------------------------
class EventCreate(BaseModel):
    """Schema for creating a new event."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: datetime
    end_time: datetime
    all_day: bool = False
    reminder_minutes_before: int = 30
    is_birthday: bool = False
    is_festival: bool = False
    festival_name: Optional[str] = None


class EventUpdate(BaseModel):
    """Schema for updating an existing event."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day: Optional[bool] = None
    reminder_minutes_before: Optional[int] = None


class EventResponse(BaseModel):
    """Schema for event response."""
    id: int
    user_id: int
    title: str
    description: Optional[str]
    location: Optional[str]
    start_time: datetime
    end_time: datetime
    all_day: bool
    reminder_minutes_before: int
    is_birthday: bool
    is_festival: bool
    festival_name: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# -----------------------------
# Dependency
# -----------------------------
async def get_current_user_id() -> int:
    """Stub for retrieving the current user ID. Replace with real auth."""
    return 1  # TODO: Replace with authentication logic


# -----------------------------
# CRUD Endpoints
# -----------------------------
@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    event: EventCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Create a new calendar event."""
    db_event = Event(user_id=user_id, **event.model_dump())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event.to_dict()


@router.get("/", response_model=List[EventResponse])
async def list_events(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """List all events for the current user with optional date filtering."""
    query = db.query(Event).filter(Event.user_id == user_id)
    if start_date:
        query = query.filter(Event.start_time >= start_date)
    if end_date:
        query = query.filter(Event.end_time <= end_date)
    events = query.order_by(Event.start_time).offset(skip).limit(limit).all()
    return [event.to_dict() for event in events]


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Retrieve a specific event by its ID."""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event.to_dict()


@router.put("/{event_id}", response_model=EventResponse)
async def update_event(
    event_id: int,
    event_update: EventUpdate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Update an existing event."""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    for key, value in event_update.model_dump(exclude_unset=True).items():
        setattr(event, key, value)
    
    db.commit()
    db.refresh(event)
    return event.to_dict()


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Delete an event."""
    event = db.query(Event).filter(Event.id == event_id, Event.user_id == user_id).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    db.delete(event)
    db.commit()
    return None
