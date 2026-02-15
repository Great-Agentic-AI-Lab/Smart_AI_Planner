"""
Task Event Hooks
Fixed: Better error handling for zero vectors
Automatically store task embeddings in Pinecone when tasks are created/updated.
"""
import logging
from typing import Optional
from app.models import Task
from app.vectordb import get_pinecone_client, get_embedding_generator

logger = logging.getLogger(__name__)


async def on_task_created(task: Task) -> bool:
    """
    Hook: Called when a task is created.
    Generates and stores embedding in Pinecone.
    Safe-fail: Returns False if operation fails, doesn't crash.
    """
    try:
        # Generate embedding
        embedding_gen = get_embedding_generator()
        embedding = await embedding_gen.generate_task_embedding(
            title=task.title,
            description=task.description,
            tags=task.tags.split(",") if task.tags else None
        )

        # Check if embedding is all zeros (failed generation)
        if all(v == 0.0 for v in embedding):
            logger.warning(f"⚠️ Embedding generation failed for task {task.id}, skipping storage")
            return False

        # Prepare metadata
        metadata = {
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority.value if task.priority else 'medium',
            'priority_score': task.priority_score or 50,
            'status': task.status.value if task.status else 'pending',
            'user_id': task.user_id,
            'created_at': task.created_at.isoformat() if task.created_at else '',
            'tags': task.tags or ''
        }

        # Store in Pinecone
        pinecone = get_pinecone_client()
        success = await pinecone.upsert_task(
            task_id=str(task.id),
            embedding=embedding,
            metadata=metadata
        )

        if success:
            logger.info(f"✅ Stored embedding for task {task.id}")

        return success

    except Exception as e:
        logger.error(f"❌ Failed to store embedding for task {task.id}: {e}")
        return False


async def on_task_completed(task: Task) -> bool:
    """
    Hook: Called when a task is marked as completed.
    Updates metadata in Pinecone with completion info.
    Safe-fail: Returns False if operation fails, doesn't crash.
    """
    try:
        # Generate embedding (in case task was updated)
        embedding_gen = get_embedding_generator()
        embedding = await embedding_gen.generate_task_embedding(
            title=task.title,
            description=task.description,
            tags=task.tags.split(",") if task.tags else None
        )

        # Check if embedding is all zeros (failed generation)
        if all(v == 0.0 for v in embedding):
            logger.warning(f"⚠️ Embedding generation failed for task {task.id}, skipping update")
            return False

        # Update metadata with completion info
        metadata = {
            'title': task.title,
            'description': task.description or '',
            'priority': task.priority.value if task.priority else 'medium',
            'priority_score': task.priority_score or 50,
            'status': 'completed',
            'user_id': task.user_id,
            'created_at': task.created_at.isoformat() if task.created_at else '',
            'completed_at': task.completed_at.isoformat() if task.completed_at else '',
            'actual_effort_minutes': task.actual_effort_minutes or 0,
            'tags': task.tags or ''
        }

        # Update in Pinecone
        pinecone = get_pinecone_client()
        success = await pinecone.upsert_task(
            task_id=str(task.id),
            embedding=embedding,
            metadata=metadata
        )

        if success:
            logger.info(f"✅ Updated completed task {task.id} in vector DB")

        return success

    except Exception as e:
        logger.error(f"❌ Failed to update completed task {task.id}: {e}")
        return False


async def on_task_deleted(task_id: int) -> bool:
    """
    Hook: Called when a task is deleted.
    Removes embedding from Pinecone.
    Safe-fail: Returns False if operation fails, doesn't crash.
    """
    try:
        pinecone = get_pinecone_client()
        success = await pinecone.delete_task(str(task_id))

        if success:
            logger.info(f"✅ Deleted task {task_id} from vector DB")

        return success

    except Exception as e:
        logger.error(f"❌ Failed to delete task {task_id}: {e}")
        return False