"""
Tasks API with Vector DB Integration
FIXED: Retry mechanism for LLM calls, proper error handling
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.database import get_db
from app.models import Task, User, TaskStatusEnum, PriorityEnum
from app.config import settings
from app.agents import get_task_planner, get_suggestion_agent
from app.vectordb.task_hooks import on_task_created, on_task_completed, on_task_deleted
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic schemas
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = []


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    actual_effort_minutes: Optional[int] = None


class TaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None
    priority_score: float
    estimated_effort_minutes: Optional[int] = None
    actual_effort_minutes: Optional[int] = None
    due_date: Optional[datetime] = None
    status: str
    tags: List[str] = Field(default_factory=list)
    postponed_count: int
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    ai_reasoning: Optional[str] = None

    class Config:
        from_attributes = True

    @field_validator('tags', mode='before')
    @classmethod
    def validate_tags(cls, v):
        """Convert string tags to list."""
        if v is None:
            return []
        if isinstance(v, str):
            return v.split(',') if v else []
        return v


# ============================================
# CREATE TASK (with embedding storage)
# ============================================

@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    """
    Create a new task with AI prioritization and vector storage.
    Includes retry mechanism for LLM calls.
    """
    try:
        # Get or create default user
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(
                telegram_id=0,
                username="api_user",
                first_name="API"
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        # Convert tags List[str] to comma-separated string for DB
        tags_str = ",".join(task_data.tags) if task_data.tags else None

        # Create task
        task = Task(
            user_id=user.id,
            title=task_data.title,
            description=task_data.description,
            due_date=task_data.due_date,
            tags=tags_str,
            status=TaskStatusEnum.PENDING
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        # AI prioritization with retry mechanism
        ai_reasoning = None
        max_retries = 3
        retry_count = 0

        try:
            # Check if API key is available before calling LLM
            if not settings.google_api_key:
                logger.warning("⚠️ GOOGLE_API_KEY not set, skipping AI prioritization")
                ai_reasoning = "AI unavailable: GOOGLE_API_KEY not configured"
            else:
                # Retry up to 3 times
                while retry_count < max_retries:
                    try:
                        logger.info(f"Calling Task Planner Agent (attempt {retry_count + 1}/{max_retries})...")
                        planner = get_task_planner()
                        result = await planner.execute(
                            title=task.title,
                            description=task.description,
                            due_date=task.due_date
                        )

                        if result['success']:
                            task.priority = PriorityEnum[result['priority'].upper()]
                            task.priority_score = result['priority_score']
                            task.estimated_effort_minutes = result['estimated_effort_minutes']
                            ai_reasoning = result['reasoning']
                            logger.info(f"✅ AI analysis succeeded on attempt {retry_count + 1}")
                            db.commit()
                            db.refresh(task)
                            break  # Success - exit retry loop
                        else:
                            ai_reasoning = f"AI analysis failed: {result.get('error')}"
                            logger.warning(f"⚠️ AI analysis failed: {ai_reasoning}")
                            break  # Fail - don't retry

                    except asyncio.TimeoutError:
                        retry_count += 1
                        logger.warning(f"⚠️ Attempt {retry_count} timed out")
                        if retry_count >= max_retries:
                            logger.error(f"❌ AI prioritization failed after {max_retries} retries (timeout)")
                            ai_reasoning = f"AI unavailable after {max_retries} retries (timeout)"
                        else:
                            logger.info(f"Retrying in 2 seconds...")
                            await asyncio.sleep(2)

                    except Exception as e:
                        retry_count += 1
                        logger.warning(f"⚠️ Attempt {retry_count} failed: {e}")
                        if retry_count >= max_retries:
                            logger.error(f"❌ AI prioritization failed after {max_retries} retries")
                            ai_reasoning = f"AI unavailable after {max_retries} retries: {str(e)}"
                        else:
                            logger.info(f"Retrying in 2 seconds...")
                            await asyncio.sleep(2)

        except Exception as e:
            logger.error(f"❌ AI prioritization outer exception: {e}")
            task.priority = PriorityEnum.MEDIUM
            task.priority_score = 50
            ai_reasoning = f"AI unavailable: {str(e)}"
            db.commit()
            db.refresh(task)

        # Store embedding in Pinecone
        try:
            await on_task_created(task)
        except Exception as e:
            logger.warning(f"⚠️ Failed to store embedding: {e}")

        # Build response - validator will handle tags conversion
        response = TaskResponse.from_orm(task)
        response.ai_reasoning = ai_reasoning
        return response

    except Exception as e:
        logger.error(f"❌ Task creation failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# UPDATE TASK (with embedding update)
# ============================================

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_data: TaskUpdate, db: Session = Depends(get_db)):
    """
    Update a task with embedding sync.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        # Track if content changed
        content_changed = False
        was_completed = task.status == TaskStatusEnum.COMPLETED

        # Update fields
        if task_data.title is not None:
            task.title = task_data.title
            content_changed = True
        if task_data.description is not None:
            task.description = task_data.description
            content_changed = True
        if task_data.due_date is not None:
            task.due_date = task_data.due_date
        if task_data.status is not None:
            task.status = TaskStatusEnum[task_data.status.upper()]
        if task_data.tags is not None:
            task.tags = ",".join(task_data.tags) if task_data.tags else None
            content_changed = True
        if task_data.actual_effort_minutes is not None:
            task.actual_effort_minutes = task_data.actual_effort_minutes

        task.updated_at = datetime.utcnow()

        # If marked as completed, set timestamp
        if task.status == TaskStatusEnum.COMPLETED and not was_completed:
            task.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(task)

        # Update embedding if content changed
        if content_changed:
            try:
                await on_task_created(task)
            except Exception as e:
                logger.warning(f"⚠️ Failed to update embedding: {e}")

        # Update completion metadata if completed
        if task.status == TaskStatusEnum.COMPLETED and not was_completed:
            try:
                await on_task_completed(task)
            except Exception as e:
                logger.warning(f"⚠️ Failed to update completion: {e}")

        response = TaskResponse.from_orm(task)
        return response

    except Exception as e:
        logger.error(f"❌ Task update failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DELETE TASK
# ============================================

@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Delete a task and its embedding."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        # Delete embedding
        try:
            await on_task_deleted(task_id)
        except Exception as e:
            logger.warning(f"⚠️ Failed to delete embedding: {e}")

        db.delete(task)
        db.commit()
        return None

    except Exception as e:
        logger.error(f"❌ Task deletion failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# LIST TASKS
# ============================================

@router.get("/", response_model=List[TaskResponse])
def list_tasks(
    status_filter: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all tasks."""
    try:
        query = db.query(Task)

        if status_filter:
            try:
                status_enum = TaskStatusEnum[status_filter.upper()]
                query = query.filter(Task.status == status_enum)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")

        tasks = query.order_by(Task.priority_score.desc()).limit(limit).all()
        return [TaskResponse.from_orm(task) for task in tasks]

    except Exception as e:
        logger.error(f"❌ Failed to list tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET TASK
# ============================================

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a specific task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_orm(task)


# ============================================
# RAG-POWERED SUGGESTION ENDPOINT
# ============================================

@router.get("/suggestions/next")
async def get_suggestion(user_id: int = 1, db: Session = Depends(get_db)):
    """Get AI-powered task recommendation using RAG."""
    try:
        # Get pending tasks for user
        pending_tasks = db.query(Task).filter(
            Task.user_id == user_id,
            Task.status == TaskStatusEnum.PENDING
        ).order_by(Task.priority_score.desc()).all()

        if not pending_tasks:
            return {
                'success': True,
                'recommended_task_id': None,
                'reasoning': 'No pending tasks! You\'re all done! 🎉',
                'alternative_tasks': [],
                'productivity_tip': 'Take a break or plan new goals!'
            }

        # Convert to dict format for agent
        tasks_data = []
        for task in pending_tasks:
            tasks_data.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'priority': task.priority.value if task.priority else 'medium',
                'priority_score': task.priority_score or 50,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'estimated_effort_minutes': task.estimated_effort_minutes
            })

        # Get AI suggestion with RAG
        suggestion_agent = get_suggestion_agent()
        result = await suggestion_agent.execute(
            pending_tasks=tasks_data,
            current_context=f"User {user_id} requesting suggestion"
        )

        return result

    except Exception as e:
        logger.error(f"❌ Suggestion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Suggestion failed: {str(e)}")