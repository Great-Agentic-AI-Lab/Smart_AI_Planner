"""
Task Management API Endpoints with AI-Powered Prioritization
Provides CRUD operations for user tasks and AI-based suggestions.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import logging

from app.database import get_db
from app.models import Task, TaskStatusEnum, PriorityEnum
from app.agents import get_task_planner

logger = logging.getLogger(__name__)
router = APIRouter()


# -----------------------------
# Pydantic Schemas
# -----------------------------
class TaskCreate(BaseModel):
    """Schema for creating a new task."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: Optional[str] = None
    context: Optional[str] = None


class TaskUpdate(BaseModel):
    """Schema for updating an existing task."""
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    status: Optional[TaskStatusEnum] = None
    tags: Optional[str] = None
    context: Optional[str] = None
    actual_effort_minutes: Optional[int] = None


class TaskResponse(BaseModel):
    """Schema for task response."""
    id: int
    user_id: int
    title: str
    description: Optional[str]
    priority: Optional[str]
    priority_score: float
    estimated_effort_minutes: Optional[int]
    actual_effort_minutes: Optional[int]
    due_date: Optional[str]
    status: str
    tags: List[str]
    postponed_count: int
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    ai_reasoning: Optional[str] = None

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
@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """Create a new task with optional AI-powered prioritization."""
    logger.info(f"Creating task: {task.title}")

    db_task = Task(user_id=user_id, **task.model_dump())
    db.add(db_task)
    db.commit()
    db.refresh(db_task)

    try:
        logger.info("Calling Task Planner Agent for AI prioritization...")
        agent = get_task_planner()
        result = await agent.execute(
            title=task.title,
            description=task.description,
            due_date=task.due_date,
            context=task.context
        )

        if result["success"]:
            db_task.priority = PriorityEnum[result["priority"].upper()]
            db_task.priority_score = result["priority_score"]
            db_task.estimated_effort_minutes = result["estimated_effort_minutes"]
            db.commit()
            db.refresh(db_task)

            response_data = db_task.to_dict()
            response_data["ai_reasoning"] = result.get("reasoning", "")
            return response_data
        else:
            response_data = db_task.to_dict()
            response_data["ai_reasoning"] = f"AI analysis failed: {result.get('error')}"
            logger.warning(response_data["ai_reasoning"])
            return response_data

    except Exception as e:
        logger.error(f"AI agent error: {e}")
        response_data = db_task.to_dict()
        response_data["ai_reasoning"] = f"AI unavailable: {str(e)}"
        return response_data


@router.get("/", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[TaskStatusEnum] = None,
    priority: Optional[PriorityEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """List tasks for the current user with optional status/priority filters."""
    query = db.query(Task).filter(Task.user_id == user_id)
    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    query = query.order_by(Task.priority_score.desc())
    tasks = query.offset(skip).limit(limit).all()
    return [task.to_dict() for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Retrieve a specific task by ID."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task.to_dict()


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(task_id: int, task_update: TaskUpdate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Update a task and optionally re-run AI analysis for priority."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    # Determine if AI re-analysis is needed
    reanalyze = any([
        task_update.title and task_update.title != task.title,
        task_update.description and task_update.description != task.description,
        task_update.due_date and task_update.due_date != task.due_date
    ])

    # Apply updates
    for key, value in task_update.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    # Mark as completed
    if task_update.status == TaskStatusEnum.COMPLETED and not task.completed_at:
        task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)

    # AI re-analysis if necessary
    if reanalyze:
        try:
            logger.info("Re-analyzing task with AI...")
            agent = get_task_planner()
            result = await agent.execute(
                title=task.title,
                description=task.description,
                due_date=task.due_date,
                context=task.context
            )
            if result["success"]:
                task.priority = PriorityEnum[result["priority"].upper()]
                task.priority_score = result["priority_score"]
                task.estimated_effort_minutes = result["estimated_effort_minutes"]
                db.commit()
                db.refresh(task)
        except Exception as e:
            logger.error(f"AI re-analysis failed: {e}")

    return task.to_dict()


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Delete a task."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    db.delete(task)
    db.commit()
    logger.info(f"Task {task_id} deleted")
    return None


@router.get("/suggestions/next")
async def get_next_task_suggestion(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Suggest the next task to work on based on AI priority."""
    task = db.query(Task).filter(Task.user_id == user_id, Task.status == TaskStatusEnum.PENDING).order_by(Task.priority_score.desc()).first()
    if not task:
        return {"suggestion": None, "message": "No pending tasks found. Great job! 🎉"}
    return {
        "suggestion": task.to_dict(),
        "message": f"I recommend working on: {task.title}",
        "reasoning": f"This task has {task.priority.value} priority (score: {task.priority_score})"
    }
