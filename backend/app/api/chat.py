"""
Chat API - Natural Language Interface
Processes user messages and performs actions using AI agents.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import logging

from app.database import get_db
from app.models import Task, User, TaskStatusEnum, PriorityEnum
from app.agents import get_task_planner, get_suggestion_agent
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)
router = APIRouter()


# Pydantic Schemas
class ChatMessage(BaseModel):
    """Request model for user chat input."""
    message: str = Field(..., description="User's message in natural language")
    user_id: int = Field(1, description="User ID (default: 1)")


class ChatResponse(BaseModel):
    """Response model from chat endpoint."""
    response: str = Field(..., description="AI-generated response text")
    action_taken: Optional[str] = Field(None, description="Action performed")
    data: Optional[Dict[str, Any]] = Field(None, description="Structured data")


# Chat Endpoint
@router.post("/", response_model=ChatResponse, summary="Natural language chat")
async def chat(message: ChatMessage, db: Session = Depends(get_db)):
    """
    Process natural language messages and perform actions.
    
    Examples:
    - "Add task: Finish report by tomorrow"
    - "What should I do next?"
    - "Show my high priority tasks"
    - "Complete task 5"
    - "How many pending tasks do I have?"
    """
    try:
        user_message = message.message.lower().strip()
        user_id = message.user_id
        
        # Get or create user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            user = User(
                telegram_id=0,
                username="chat_user",
                first_name="Chat User"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Intent Detection & Action
        
        # 1. ADD TASK
        if any(word in user_message for word in ['add task', 'create task', 'new task', 'remind me']):
            return await _handle_add_task(user_message, user_id, db)
        
        # 2. LIST TASKS
        elif any(word in user_message for word in ['show tasks', 'list tasks', 'my tasks', 'what tasks']):
            return await _handle_list_tasks(user_id, db)
        
        # 3. COMPLETE TASK
        elif 'complete' in user_message or 'done' in user_message or 'finish' in user_message:
            return await _handle_complete_task(user_message, user_id, db)
        
        # 4. GET SUGGESTION
        elif any(word in user_message for word in ['what next', 'recommend', 'suggest', 'what should i']):
            return await _handle_suggestion(user_id, db)
        
        # 5. COUNT TASKS
        elif 'how many' in user_message:
            return await _handle_count_tasks(user_id, db)
        
        # 6. DELETE TASK
        elif 'delete' in user_message or 'remove' in user_message:
            return await _handle_delete_task(user_message, user_id, db)
        
        # 7. GENERAL QUERY
        else:
            return ChatResponse(
                response="I can help you with tasks! Try:\n"
                         "• 'Add task: [task name]'\n"
                         "• 'What should I do next?'\n"
                         "• 'Show my tasks'\n"
                         "• 'Complete task 5'\n"
                         "• 'How many tasks do I have?'",
                action_taken=None,
                data=None
            )
    
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Helper Functions

async def _handle_add_task(message: str, user_id: int, db: Session) -> ChatResponse:
    """Extract task details and create task."""
    try:
        # Extract task title
        title = None
        for prefix in ['add task:', 'create task:', 'new task:', 'remind me to', 'remind me:']:
            if prefix in message:
                title = message.split(prefix, 1)[1].strip()
                break
        
        if not title:
            return ChatResponse(
                response="Please specify the task. Example: 'Add task: Buy groceries'",
                action_taken=None
            )
        
        # Extract due date
        due_date = None
        if 'tomorrow' in message:
            due_date = datetime.utcnow() + timedelta(days=1)
        elif 'today' in message:
            due_date = datetime.utcnow()
        elif match := re.search(r'in (\d+) days?', message):
            due_date = datetime.utcnow() + timedelta(days=int(match.group(1)))
        
        # Create task
        task = Task(
            user_id=user_id,
            title=title,
            due_date=due_date,
            status=TaskStatusEnum.PENDING
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # AI prioritization
        try:
            agent = get_task_planner()
            result = await agent.execute(title=title, due_date=due_date)
            
            if result['success']:
                task.priority = PriorityEnum[result['priority'].upper()]
                task.priority_score = result['priority_score']
                task.estimated_effort_minutes = result['estimated_effort_minutes']
                db.commit()
                db.refresh(task)
        except Exception as e:
            logger.error(f"AI prioritization failed: {e}")
        
        return ChatResponse(
            response=f"Task created: {title}\n"
                    f"Priority: {task.priority.value.upper() if task.priority else 'MEDIUM'}\n"
                    f"Due: {due_date.strftime('%d %b %Y') if due_date else 'No deadline'}",
            action_taken="task_created",
            data={"task_id": task.id, "title": title}
        )
    
    except Exception as e:
        logger.error(f"Add task error: {e}")
        return ChatResponse(
            response=f"Failed to create task: {str(e)}",
            action_taken="error"
        )


async def _handle_list_tasks(user_id: int, db: Session) -> ChatResponse:
    """List user's pending tasks."""
    tasks = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status == TaskStatusEnum.PENDING
    ).order_by(Task.priority_score.desc()).limit(10).all()
    
    if not tasks:
        return ChatResponse(
            response="🎉 You have no pending tasks! Great job!",
            action_taken="list_tasks",
            data={"count": 0}
        )
    
    task_list = "Your Tasks:\n\n"
    for i, task in enumerate(tasks, 1):
        priority_emoji = {
            PriorityEnum.HIGH: '🔴',
            PriorityEnum.MEDIUM: '🟡',
            PriorityEnum.LOW: '🟢'
        }
        emoji = priority_emoji.get(task.priority, '⚪')
        due_text = f"Due: {task.due_date.strftime('%d %b')}" if task.due_date else "No deadline"
        task_list += f"{emoji} {i}. {task.title} (#{task.id})\n   {due_text}\n\n"
    
    return ChatResponse(
        response=task_list,
        action_taken="list_tasks",
        data={"count": len(tasks), "tasks": [t.id for t in tasks]}
    )


async def _handle_complete_task(message: str, user_id: int, db: Session) -> ChatResponse:
    """Mark task as complete."""
    # Extract task ID
    match = re.search(r'\d+', message)
    if not match:
        return ChatResponse(
            response="Please specify task ID. Example: 'Complete task 5'",
            action_taken=None
        )
    
    task_id = int(match.group())
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user_id
    ).first()
    
    if not task:
        return ChatResponse(
            response=f"Task #{task_id} not found",
            action_taken="error"
        )
    
    task.status = TaskStatusEnum.COMPLETED
    task.completed_at = datetime.utcnow()
    db.commit()
    
    return ChatResponse(
        response=f"Completed: {task.title}\n\n🎉 Great job!",
        action_taken="task_completed",
        data={"task_id": task_id, "title": task.title}
    )


async def _handle_suggestion(user_id: int, db: Session) -> ChatResponse:
    """Get AI task suggestion."""
    task = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status == TaskStatusEnum.PENDING
    ).order_by(Task.priority_score.desc()).first()
    
    if not task:
        return ChatResponse(
            response="No pending tasks! You're all caught up!",
            action_taken="suggestion",
            data=None
        )
    
    priority_emoji = {
        PriorityEnum.HIGH: '🔴',
        PriorityEnum.MEDIUM: '🟡',
        PriorityEnum.LOW: '🟢'
    }
    emoji = priority_emoji.get(task.priority, '⚪')
    
    return ChatResponse(
        response=f"I recommend working on:\n\n"
                f"{emoji} {task.title}\n"
                f"Priority: {task.priority.value.upper() if task.priority else 'MEDIUM'}\n"
                f"Estimated time: {task.estimated_effort_minutes or '?'} min",
        action_taken="suggestion",
        data={"task_id": task.id, "title": task.title}
    )


async def _handle_count_tasks(user_id: int, db: Session) -> ChatResponse:
    """Count user's tasks."""
    pending = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status == TaskStatusEnum.PENDING
    ).count()
    
    completed = db.query(Task).filter(
        Task.user_id == user_id,
        Task.status == TaskStatusEnum.COMPLETED
    ).count()
    
    return ChatResponse(
        response=f"Task Summary:\n\n"
                f"Pending: {pending}\n"
                f"Completed: {completed}\n"
                f"Total: {pending + completed}",
        action_taken="count_tasks",
        data={"pending": pending, "completed": completed}
    )


async def _handle_delete_task(message: str, user_id: int, db: Session) -> ChatResponse:
    """Delete a task."""
    match = re.search(r'\d+', message)
    if not match:
        return ChatResponse(
            response="Please specify task ID. Example: 'Delete task 5'",
            action_taken=None
        )
    
    task_id = int(match.group())
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == user_id
    ).first()
    
    if not task:
        return ChatResponse(
            response=f"Task #{task_id} not found",
            action_taken="error"
        )
    
    title = task.title
    db.delete(task)
    db.commit()
    
    return ChatResponse(
        response=f"Deleted: {title}",
        action_taken="task_deleted",
        data={"task_id": task_id, "title": title}
    )