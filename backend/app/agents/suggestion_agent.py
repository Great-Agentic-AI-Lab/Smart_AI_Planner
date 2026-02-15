"""
Suggestion Agent
Provides intelligent task recommendations using RAG (Retrieval Augmented Generation).
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

from app.agents.base_agent import BaseAgent
from app.vectordb.pinecone_client import get_pinecone_client
from app.vectordb.embeddings import get_embedding_generator

logger = logging.getLogger(__name__)


class SuggestionAgent(BaseAgent):
    """
    AI agent that suggests what task to work on next.
    
    Uses RAG to find similar completed tasks and learn from past patterns.
    Considers: priority, due dates, time of day, similar past tasks.
    """
    
    SYSTEM_PROMPT = """You are an intelligent task recommendation AI.

Your job is to suggest which task the user should work on next based on:
1. Current pending tasks with priorities
2. Similar tasks completed in the past (from context)
3. Time of day and user patterns
4. Urgency and deadlines

Respond with JSON:
{
    "recommended_task_id": <id>,
    "reasoning": "clear explanation of why this task",
    "alternative_tasks": [<id>, <id>],
    "productivity_tip": "helpful tip for completing this task"
}

Be encouraging and motivational. Help users make smart decisions.
"""
    
    def __init__(self):
        super().__init__(
            name="SuggestionAgent",
            system_prompt=self.SYSTEM_PROMPT,
            temperature=0.7  # Slightly creative for tips
        )
        self.pinecone = get_pinecone_client()
        self.embedding_gen = get_embedding_generator()
    
    async def execute(
        self,
        pending_tasks: List[Dict[str, Any]],
        current_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Suggest next task to work on.
        
        Args:
            pending_tasks: List of pending tasks with metadata
            current_context: Optional context (time of day, location, etc.)
            
        Returns:
            Suggestion with reasoning and alternatives
        """
        logger.info("🤔 Generating task suggestion...")
        
        if not pending_tasks:
            return {
                'success': True,
                'recommended_task_id': None,
                'reasoning': 'No pending tasks! Take a break or add new ones.',
                'alternative_tasks': [],
                'productivity_tip': 'Great job staying on top of everything!'
            }
        
        try:
            # Step 1: Find similar completed tasks (RAG)
            similar_context = await self._get_similar_tasks_context(pending_tasks)
            
            # Step 2: Build comprehensive prompt
            prompt = self._build_suggestion_prompt(
                pending_tasks,
                similar_context,
                current_context
            )
            
            # Step 3: Ask AI for recommendation
            result = await self._call_llm(prompt, parse_json=True)
            
            if result['success']:
                suggestion = result['data']
                logger.info(f"✅ Suggested task ID: {suggestion.get('recommended_task_id')}")
                return {
                    'success': True,
                    **suggestion
                }
            else:
                # Fallback: suggest highest priority
                return self._fallback_suggestion(pending_tasks)
                
        except Exception as e:
            logger.error(f"❌ Suggestion failed: {e}")
            return self._fallback_suggestion(pending_tasks)
    
    async def _get_similar_tasks_context(
        self,
        pending_tasks: List[Dict[str, Any]]
    ) -> str:
        """
        Use RAG to find similar completed tasks.
        Helps AI learn from past patterns.
        """
        try:
            # Get embeddings for top 3 pending tasks
            top_tasks = sorted(
                pending_tasks,
                key=lambda x: x.get('priority_score', 0),
                reverse=True
            )[:3]
            
            similar_tasks_text = []
            
            for task in top_tasks:
                # Generate query embedding
                query_embedding = await self.embedding_gen.generate_task_embedding(
                    title=task['title'],
                    description=task.get('description')
                )
                
                # Search for similar completed tasks
                similar = await self.pinecone.search_similar(
                    query_embedding=query_embedding,
                    top_k=3,
                    filter_dict={"status": "completed"}
                )
                
                if similar:
                    for sim_task in similar:
                        metadata = sim_task['metadata']
                        similar_tasks_text.append(
                            f"Previously completed: '{metadata.get('title')}' "
                            f"(Priority: {metadata.get('priority')}, "
                            f"Effort: {metadata.get('actual_effort_minutes')}min)"
                        )
            
            if similar_tasks_text:
                return "\\n".join(similar_tasks_text)
            else:
                return "No similar past tasks found (user is new or few completed tasks)."
                
        except Exception as e:
            logger.warning(f"⚠️ RAG lookup failed: {e}")
            return "Past task history unavailable."
    
    def _build_suggestion_prompt(
        self,
        pending_tasks: List[Dict[str, Any]],
        similar_context: str,
        current_context: Optional[str]
    ) -> str:
        """Build comprehensive prompt for AI."""
        # Current time context
        now = datetime.utcnow()
        time_context = f"Current time: {now.strftime('%A, %H:%M UTC')}"
        if now.hour < 12:
            time_context += " (Morning - good for focused work)"
        elif now.hour < 17:
            time_context += " (Afternoon - good for collaboration)"
        else:
            time_context += " (Evening - good for planning/admin)"
        
        # Format pending tasks
        tasks_list = []
        for task in pending_tasks:
            due_text = task.get('due_date', 'No deadline')
            if isinstance(due_text, str) and 'T' in due_text:
                try:
                    due_dt = datetime.fromisoformat(due_text.replace('Z', '+00:00'))
                    due_text = due_dt.strftime('%Y-%m-%d')
                except:
                    pass
            
            tasks_list.append(
                f"ID {task['id']}: {task['title']} | "
                f"Priority: {task.get('priority', 'medium')} ({task.get('priority_score', 50)}/100) | "
                f"Due: {due_text} | "
                f"Est: {task.get('estimated_effort_minutes', '?')}min"
            )
        
        prompt = f"""
{time_context}

PENDING TASKS:
{chr(10).join(tasks_list)}

SIMILAR PAST TASKS:
{similar_context}

{f'ADDITIONAL CONTEXT: {current_context}' if current_context else ''}

Based on priorities, deadlines, time of day, and past patterns, recommend ONE task to work on next.
Provide 2-3 alternatives and a helpful productivity tip.
"""
        
        return prompt
    
    def _fallback_suggestion(self, pending_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simple fallback: suggest highest priority task."""
        sorted_tasks = sorted(
            pending_tasks,
            key=lambda x: x.get('priority_score', 0),
            reverse=True
        )
        
        recommended = sorted_tasks[0]
        alternatives = [t['id'] for t in sorted_tasks[1:3]]
        
        return {
            'success': True,
            'recommended_task_id': recommended['id'],
            'reasoning': f"Highest priority task ({recommended.get('priority_score', 50)}/100)",
            'alternative_tasks': alternatives,
            'productivity_tip': 'Start with the most important task when you have the most energy!'
        }


# Singleton
_suggestion_agent: Optional[SuggestionAgent] = None


def get_suggestion_agent() -> SuggestionAgent:
    """Get or create Suggestion Agent singleton."""
    global _suggestion_agent
    if _suggestion_agent is None:
        _suggestion_agent = SuggestionAgent()
    return _suggestion_agent
