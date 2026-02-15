"""
Analytics Agent
Analyzes productivity patterns and provides insights.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter
import logging

from app.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class AnalyticsAgent(BaseAgent):
    """
    AI agent that analyzes user productivity and provides insights.
    
    Features:
    - Completion rate analysis
    - Time-of-day productivity patterns
    - Task category insights
    - Weekly/monthly reports
    - Personalized productivity tips
    """
    
    SYSTEM_PROMPT = """You are a productivity analytics expert.

Your job is to analyze user task data and provide actionable insights.

Focus on:
- Completion patterns (when, what, how long)
- Productivity trends (improving/declining)
- Bottlenecks and challenges
- Personalized recommendations

Respond with JSON:
{
    "overall_score": <0-100>,
    "key_insights": ["insight 1", "insight 2", "insight 3"],
    "productivity_trends": "improving/stable/declining",
    "recommendations": ["action 1", "action 2"],
    "celebration": "positive message about achievements"
}

Be encouraging, data-driven, and actionable. Help users improve without being judgmental.
"""
    
    def __init__(self):
        super().__init__(
            name="AnalyticsAgent",
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.5  # Balanced creativity and consistency
        )
    
    async def generate_weekly_report(
        self,
        completed_tasks: List[Dict[str, Any]],
        pending_tasks: List[Dict[str, Any]],
        period_days: int = 7
    ) -> Dict[str, Any]:
        """
        Generate weekly productivity report.
        
        Args:
            completed_tasks: Tasks completed in the period
            pending_tasks: Currently pending tasks
            period_days: Analysis period (default 7 days)
            
        Returns:
            Comprehensive productivity report with insights
        """
        logger.info(f"📊 Generating {period_days}-day analytics report...")
        
        try:
            # Calculate statistics
            stats = self._calculate_statistics(completed_tasks, pending_tasks, period_days)
            
            # Build analysis prompt
            prompt = self._build_analytics_prompt(stats)
            
            # Ask AI for insights
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                insights = result['data']
                logger.info(f"✅ Generated analytics: {insights.get('overall_score')}/100")
                return {
                    'success': True,
                    'period_days': period_days,
                    'statistics': stats,
                    **insights
                }
            else:
                return self._fallback_report(stats, period_days)
                
        except Exception as e:
            logger.error(f"❌ Analytics generation failed: {e}")
            return self._fallback_report({}, period_days)
    
    async def get_productivity_insights(
        self,
        user_id: int,
        completed_tasks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get quick productivity insights.
        
        Args:
            user_id: User identifier
            completed_tasks: Recent completed tasks
            
        Returns:
            Quick insights and tips
        """
        logger.info(f"💡 Generating productivity insights for user {user_id}")
        
        try:
            # Analyze patterns
            patterns = self._analyze_patterns(completed_tasks)
            
            # Build prompt
            prompt = f"""
Analyze these productivity patterns:

{patterns}

Provide 3 quick insights and 2 actionable tips to improve productivity.
"""
            
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                return {
                    'success': True,
                    **result['data'],
                    'patterns': patterns
                }
            else:
                return {
                    'success': True,
                    'key_insights': ['Keep completing tasks to see patterns!'],
                    'recommendations': ['Set realistic deadlines', 'Break large tasks into smaller ones']
                }
                
        except Exception as e:
            logger.error(f"❌ Insights generation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _calculate_statistics(
        self,
        completed_tasks: List[Dict[str, Any]],
        pending_tasks: List[Dict[str, Any]],
        period_days: int
    ) -> Dict[str, Any]:
        """Calculate comprehensive statistics."""
        
        total_completed = len(completed_tasks)
        total_pending = len(pending_tasks)
        
        # Completion rate
        total_tasks = total_completed + total_pending
        completion_rate = (total_completed / total_tasks * 100) if total_tasks > 0 else 0
        
        # Average effort
        efforts = [t.get('actual_effort_minutes', 0) for t in completed_tasks if t.get('actual_effort_minutes')]
        avg_effort = sum(efforts) / len(efforts) if efforts else 0
        
        # Priority distribution
        priority_counts = Counter([t.get('priority', 'medium') for t in completed_tasks])
        
        # Time-of-day analysis
        completion_hours = []
        for task in completed_tasks:
            completed_at = task.get('completed_at')
            if completed_at:
                try:
                    if isinstance(completed_at, str):
                        dt = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                    else:
                        dt = completed_at
                    completion_hours.append(dt.hour)
                except:
                    pass
        
        # Most productive hour
        if completion_hours:
            most_productive_hour = Counter(completion_hours).most_common(1)[0][0]
            if most_productive_hour < 12:
                productivity_time = "morning"
            elif most_productive_hour < 17:
                productivity_time = "afternoon"
            else:
                productivity_time = "evening"
        else:
            productivity_time = "unknown"
        
        # Overdue analysis
        overdue_count = sum(1 for t in pending_tasks if self._is_overdue(t))
        
        # Task categories (based on keywords)
        categories = self._categorize_tasks(completed_tasks)
        
        return {
            'period_days': period_days,
            'total_completed': total_completed,
            'total_pending': total_pending,
            'completion_rate': round(completion_rate, 1),
            'avg_effort_minutes': round(avg_effort, 1),
            'high_priority_completed': priority_counts.get('high', 0),
            'medium_priority_completed': priority_counts.get('medium', 0),
            'low_priority_completed': priority_counts.get('low', 0),
            'most_productive_time': productivity_time,
            'overdue_count': overdue_count,
            'top_categories': categories.most_common(3),
            'tasks_per_day': round(total_completed / period_days, 1)
        }
    
    def _analyze_patterns(self, completed_tasks: List[Dict[str, Any]]) -> str:
        """Analyze completion patterns."""
        if not completed_tasks:
            return "No completed tasks to analyze yet."
        
        patterns = []
        
        # Completion frequency
        patterns.append(f"Completed {len(completed_tasks)} tasks recently")
        
        # Priority focus
        priority_counts = Counter([t.get('priority', 'medium') for t in completed_tasks])
        top_priority = priority_counts.most_common(1)[0][0] if priority_counts else 'unknown'
        patterns.append(f"Focuses mostly on {top_priority} priority tasks")
        
        # Effort patterns
        efforts = [t.get('actual_effort_minutes', 0) for t in completed_tasks if t.get('actual_effort_minutes')]
        if efforts:
            avg_effort = sum(efforts) / len(efforts)
            patterns.append(f"Average task completion time: {int(avg_effort)} minutes")
        
        return " | ".join(patterns)
    
    def _categorize_tasks(self, tasks: List[Dict[str, Any]]) -> Counter:
        """Categorize tasks based on title keywords."""
        categories = []
        
        category_keywords = {
            'work': ['meeting', 'report', 'email', 'presentation', 'project'],
            'personal': ['buy', 'call', 'family', 'health', 'exercise'],
            'learning': ['read', 'study', 'learn', 'course', 'tutorial'],
            'admin': ['pay', 'bill', 'tax', 'document', 'form']
        }
        
        for task in tasks:
            title = task.get('title', '').lower()
            categorized = False
            
            for category, keywords in category_keywords.items():
                if any(keyword in title for keyword in keywords):
                    categories.append(category)
                    categorized = True
                    break
            
            if not categorized:
                categories.append('other')
        
        return Counter(categories)
    
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
    
    def _build_analytics_prompt(self, stats: Dict[str, Any]) -> str:
        """Build comprehensive analytics prompt."""
        
        prompt = f"""
Analyze this {stats['period_days']}-day productivity data:

COMPLETION METRICS:
- Tasks completed: {stats['total_completed']}
- Tasks pending: {stats['total_pending']}
- Completion rate: {stats['completion_rate']}%
- Tasks per day: {stats['tasks_per_day']}

EFFORT & PRIORITY:
- Average effort: {stats['avg_effort_minutes']} minutes
- High priority completed: {stats['high_priority_completed']}
- Medium priority completed: {stats['medium_priority_completed']}
- Low priority completed: {stats['low_priority_completed']}

PATTERNS:
- Most productive time: {stats['most_productive_time']}
- Overdue tasks: {stats['overdue_count']}
- Top categories: {stats['top_categories']}

Provide:
1. Overall productivity score (0-100)
2. 3-5 key insights
3. Trend assessment (improving/stable/declining)
4. Specific recommendations to improve
5. Positive celebration message
"""
        
        return prompt
    
    def _fallback_report(self, stats: Dict[str, Any], period_days: int) -> Dict[str, Any]:
        """Simple fallback report without AI."""
        
        completion_rate = stats.get('completion_rate', 0)
        
        if completion_rate >= 70:
            score = 80
            trend = "improving"
            celebration = "🎉 Excellent work! You're crushing it!"
        elif completion_rate >= 40:
            score = 60
            trend = "stable"
            celebration = "👍 Good progress! Keep it up!"
        else:
            score = 40
            trend = "needs_attention"
            celebration = "💪 Every task completed is progress!"
        
        return {
            'success': True,
            'period_days': period_days,
            'statistics': stats,
            'overall_score': score,
            'key_insights': [
                f"Completion rate: {stats.get('completion_rate', 0)}%",
                f"Most productive during {stats.get('most_productive_time', 'unknown')}",
                f"Completed {stats.get('total_completed', 0)} tasks"
            ],
            'productivity_trends': trend,
            'recommendations': [
                "Set realistic deadlines",
                "Break large tasks into smaller ones",
                "Focus on high-priority items first"
            ],
            'celebration': celebration
        }


# Singleton
_analytics_agent: Optional[AnalyticsAgent] = None


def get_analytics_agent() -> AnalyticsAgent:
    """Get or create Analytics Agent singleton."""
    global _analytics_agent
    if _analytics_agent is None:
        _analytics_agent = AnalyticsAgent()
    return _analytics_agent
