"""
Notification Agent
Sends intelligent task reminders and daily digests.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class NotificationAgent(BaseAgent):
    """
    AI agent that sends task reminders and notifications.
    
    Features:
    - Due date reminders (2 hours before, 1 day before)
    - Daily digest of upcoming tasks
    - Overdue task alerts
    - Smart timing based on user patterns
    """
    
    SYSTEM_PROMPT = """You are a helpful notification assistant.

Your job is to create motivating, friendly reminder messages for tasks.

Consider:
- Task priority and urgency
- User's productivity patterns
- Encouraging but not annoying tone
- Clear action items

Respond with JSON:
{
    "message": "short, friendly reminder text",
    "urgency_level": "high/medium/low",
    "suggested_action": "what user should do now"
}

Be supportive and positive. Help users stay on track without stress.
"""
    
    def __init__(self):
        super().__init__(
            name="NotificationAgent",
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.6  # Friendly but consistent
        )
    
    async def generate_task_reminder(
        self,
        task: Dict[str, Any],
        reminder_type: str = "upcoming"
    ) -> Dict[str, Any]:
        """
        Generate a reminder message for a task.
        
        Args:
            task: Task data (title, due_date, priority, etc.)
            reminder_type: "upcoming", "overdue", "today", "digest"
            
        Returns:
            Reminder message with urgency and suggested action
        """
        logger.info(f"📬 Generating {reminder_type} reminder for task {task.get('id')}")
        
        try:
            # Build context-aware prompt
            prompt = self._build_reminder_prompt(task, reminder_type)
            
            # Ask AI for reminder
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                notification = result['data']
                logger.info(f"✅ Generated reminder: {notification.get('message')[:50]}...")
                return {
                    'success': True,
                    **notification
                }
            else:
                return self._fallback_reminder(task, reminder_type)
                
        except Exception as e:
            logger.error(f"❌ Reminder generation failed: {e}")
            return self._fallback_reminder(task, reminder_type)
    
    async def generate_daily_digest(
        self,
        tasks: List[Dict[str, Any]],
        user_stats: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a daily digest of tasks and productivity insights.
        
        Args:
            tasks: List of pending tasks
            user_stats: Optional productivity statistics
            
        Returns:
            Daily digest message with task summary and motivation
        """
        logger.info("📊 Generating daily digest...")
        
        try:
            # Categorize tasks
            overdue = [t for t in tasks if self._is_overdue(t)]
            today = [t for t in tasks if self._is_due_today(t)]
            upcoming = [t for t in tasks if self._is_upcoming(t)]
            
            # Build digest prompt
            prompt = self._build_digest_prompt(overdue, today, upcoming, user_stats)
            
            # Ask AI for digest
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                digest = result['data']
                logger.info("✅ Generated daily digest")
                return {
                    'success': True,
                    **digest,
                    'stats': {
                        'overdue_count': len(overdue),
                        'today_count': len(today),
                        'upcoming_count': len(upcoming)
                    }
                }
            else:
                return self._fallback_digest(overdue, today, upcoming)
                
        except Exception as e:
            logger.error(f"❌ Digest generation failed: {e}")
            return self._fallback_digest([], [], [])
    
    def _build_reminder_prompt(self, task: Dict[str, Any], reminder_type: str) -> str:
        """Build context-aware reminder prompt."""
        title = task.get('title', 'Unknown task')
        priority = task.get('priority', 'medium')
        due_date = task.get('due_date')
        estimated_minutes = task.get('estimated_effort_minutes', '?')
        
        # Calculate time until due
        time_context = ""
        if due_date:
            try:
                if isinstance(due_date, str):
                    due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                else:
                    due_dt = due_date
                
                now = datetime.utcnow()
                time_diff = due_dt - now
                hours_left = time_diff.total_seconds() / 3600
                
                if hours_left < 0:
                    time_context = f"OVERDUE by {abs(int(hours_left))} hours"
                elif hours_left < 2:
                    time_context = f"Due in {int(hours_left * 60)} minutes"
                elif hours_left < 24:
                    time_context = f"Due in {int(hours_left)} hours"
                else:
                    time_context = f"Due in {int(hours_left / 24)} days"
            except:
                time_context = "Due date unknown"
        
        prompt = f"""
Task: "{title}"
Priority: {priority.upper()}
{time_context}
Estimated effort: {estimated_minutes} minutes
Reminder type: {reminder_type}

Create a {reminder_type} reminder that is:
- Motivating and friendly
- Clear about urgency
- Suggests specific action
"""
        
        return prompt
    
    def _build_digest_prompt(
        self,
        overdue: List[Dict],
        today: List[Dict],
        upcoming: List[Dict],
        user_stats: Optional[Dict]
    ) -> str:
        """Build daily digest prompt."""
        
        stats_text = ""
        if user_stats:
            stats_text = f"\nUser productivity stats: {user_stats}"
        
        prompt = f"""
Create a daily digest for the user.

OVERDUE TASKS ({len(overdue)}):
{self._format_task_list(overdue)}

DUE TODAY ({len(today)}):
{self._format_task_list(today)}

UPCOMING ({len(upcoming)}):
{self._format_task_list(upcoming)}

{stats_text}

Generate:
- message: friendly daily summary
- priority_focus: which tasks to tackle first
- motivation_tip: encouraging productivity advice
"""
        
        return prompt
    
    def _format_task_list(self, tasks: List[Dict]) -> str:
        """Format task list for prompt."""
        if not tasks:
            return "None"
        
        formatted = []
        for task in tasks[:5]:  # Limit to 5 tasks
            formatted.append(f"- {task.get('title')} (Priority: {task.get('priority', 'medium')})")
        
        if len(tasks) > 5:
            formatted.append(f"... and {len(tasks) - 5} more")
        
        return "\n".join(formatted)
    
    def _is_overdue(self, task: Dict[str, Any]) -> bool:
        """Check if task is overdue."""
        due_date = task.get('due_date')
        if not due_date:
            return False
        
        try:
            if isinstance(due_date, str):
                due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            else:
                due_dt = due_date
            return due_dt < datetime.utcnow()
        except:
            return False
    
    def _is_due_today(self, task: Dict[str, Any]) -> bool:
        """Check if task is due today."""
        due_date = task.get('due_date')
        if not due_date:
            return False
        
        try:
            if isinstance(due_date, str):
                due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            else:
                due_dt = due_date
            now = datetime.utcnow()
            return due_dt.date() == now.date()
        except:
            return False
    
    def _is_upcoming(self, task: Dict[str, Any]) -> bool:
        """Check if task is upcoming (next 7 days)."""
        due_date = task.get('due_date')
        if not due_date:
            return False
        
        try:
            if isinstance(due_date, str):
                due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
            else:
                due_dt = due_date
            now = datetime.utcnow()
            return due_dt > now and due_dt < (now + timedelta(days=7))
        except:
            return False
    
    def _fallback_reminder(self, task: Dict[str, Any], reminder_type: str) -> Dict[str, Any]:
        """Simple fallback reminder without AI."""
        title = task.get('title', 'Your task')
        
        messages = {
            'upcoming': f"⏰ Reminder: {title} is coming up soon!",
            'overdue': f"🚨 {title} is overdue. Please complete it ASAP!",
            'today': f"📅 {title} is due today. Time to work on it!",
            'digest': "Good morning! You have pending tasks to review."
        }
        
        return {
            'success': True,
            'message': messages.get(reminder_type, f"Reminder: {title}"),
            'urgency_level': 'medium',
            'suggested_action': 'Review and prioritize your tasks'
        }
    
    def _fallback_digest(
        self,
        overdue: List[Dict],
        today: List[Dict],
        upcoming: List[Dict]
    ) -> Dict[str, Any]:
        """Simple fallback digest."""
        return {
            'success': True,
            'message': f"Good morning! You have {len(overdue)} overdue, {len(today)} due today, and {len(upcoming)} upcoming tasks.",
            'priority_focus': 'Start with overdue tasks first',
            'motivation_tip': 'One task at a time. You got this!',
            'stats': {
                'overdue_count': len(overdue),
                'today_count': len(today),
                'upcoming_count': len(upcoming)
            }
        }


# Singleton
_notification_agent: Optional[NotificationAgent] = None


def get_notification_agent() -> NotificationAgent:
    """Get or create Notification Agent singleton."""
    global _notification_agent
    if _notification_agent is None:
        _notification_agent = NotificationAgent()
    return _notification_agent
