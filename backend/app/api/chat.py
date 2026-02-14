"""
Chat interface API for natural language task and event management.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict

router = APIRouter()


# -----------------------------
# Pydantic Schemas
# -----------------------------
class ChatMessage(BaseModel):
    """Request model for user chat input."""
    message: str = Field(..., description="User's message in natural language")
    user_id: Optional[int] = Field(None, description="Optional user ID for context")


class ChatResponse(BaseModel):
    """Response model returned from the chat endpoint."""
    response: str = Field(..., description="AI-generated response text")
    action_taken: Optional[str] = Field(None, description="Optional action performed, e.g., task created")
    data: Optional[Dict] = Field(None, description="Optional structured data returned, e.g., task details")


# -----------------------------
# Chat Endpoint
# -----------------------------
@router.post("/", response_model=ChatResponse, summary="Process a natural language chat message")
async def chat(message: ChatMessage):
    """
    Process a natural language message from the user and optionally perform actions.

    Examples:
        - "Add task: Finish project report by tomorrow"
        - "What should I do next?"
        - "Show me my tasks for today"
        - "Delete task 5"

    Returns:
        ChatResponse: AI-generated response with optional action and data
    """
    # TODO: Integrate with AI agents (Gemini, Perplexity, etc.)
    # Example placeholder response
    return ChatResponse(
        response="Chat interface coming soon! Use the API endpoints directly for now.",
        action_taken=None,
        data=None
    )
