"""
Task Planner Agent
Analyzes tasks and assigns priority and effort estimation.
"""

from typing import Dict, Any, Optional, Literal
from datetime import datetime
import logging

from pydantic import BaseModel, Field, ValidationError

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class TaskAnalysis(BaseModel):
    priority: Literal["high", "medium", "low"]
    priority_score: int = Field(ge=0, le=100)
    estimated_effort_minutes: int = Field(ge=0)
    category: str
    reasoning: str


class TaskPlannerAgent(BaseAgent):
    """
    Analyzes tasks and provides:
    - priority level
    - priority score
    - estimated effort
    - category
    - reasoning
    """

    SYSTEM_PROMPT = """
You are an expert task management AI assistant.

Analyze tasks and return structured JSON with:

priority (high | medium | low)
priority_score (0-100)
estimated_effort_minutes (integer)
category (string)
reasoning (string)

Priority Guidelines:
- HIGH (80-100): Urgent deadlines within 24hrs, critical importance
- MEDIUM (40-79): Important but not urgent
- LOW (0-39): Minimal urgency or impact

Effort Estimation:
- Simple: 5-15 minutes
- Moderate: 30-120 minutes
- Complex: 180+ minutes

Respond with ONLY valid JSON.
"""

    def __init__(self):
        super().__init__(
            name="TaskPlannerAgent",
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.0,
        )

    async def execute(
        self,
        title: str,
        description: Optional[str] = None,
        due_date: Optional[datetime] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:

        logger.info("Analyzing task: %s", title)

        parts = [f"Task: {title}"]

        if description:
            parts.append(f"Description: {description}")

        if due_date:
    # Make timezone-naive for comparison
            if due_date.tzinfo is not None:
                due_date = due_date.replace(tzinfo=None)
    
            now = datetime.utcnow()
            time_until = due_date - now
            hours_until = time_until.total_seconds() / 3600

            if hours_until < 24:
                urgency = "VERY URGENT - due within 24 hours"
            elif hours_until < 48:
                urgency = "URGENT - due within 2 days"
            elif hours_until < 168:  # 1 week
                urgency = "Moderate urgency - due within a week"
            else:
                urgency = "Low urgency - deadline is far"

            parts.append(f"Due Date: {due_date.strftime('%Y-%m-%d %H:%M')}")
            parts.append(f"Urgency: {urgency}")
        else:
            parts.append("Due Date: Not specified (assume low urgency)")

        if context:
            parts.append(f"Additional Context: {context}")

        parts.append(
            f"Current Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
        )

        user_prompt = "\n".join(parts)

        result = await self._call_llm(user_prompt, parse_json=True)

        if not result["success"]:
            logger.error("Task analysis failed: %s", result.get("error"))
            return self._default_response(error=result.get("error"))

        try:
            analysis = TaskAnalysis(**result["data"])

            logger.info(
                "Task analyzed: %s (score: %s)",
                analysis.priority,
                analysis.priority_score,
            )

            return {
                "success": True,
                "priority": analysis.priority,
                "priority_score": analysis.priority_score,
                "estimated_effort_minutes": analysis.estimated_effort_minutes,
                "category": analysis.category,
                "reasoning": analysis.reasoning,
            }

        except ValidationError as e:
            logger.error("Structured validation failed: %s", str(e))
            return self._default_response(error="Invalid structured output")

    def _default_response(self, error: Optional[str] = None) -> Dict[str, Any]:
        return {
            "success": False,
            "error": error,
            "priority": "medium",
            "priority_score": 50,
            "estimated_effort_minutes": 30,
            "category": "general",
            "reasoning": "Analysis failed. Default values applied.",
        }


_task_planner: Optional[TaskPlannerAgent] = None


def get_task_planner() -> TaskPlannerAgent:
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlannerAgent()
    return _task_planner
