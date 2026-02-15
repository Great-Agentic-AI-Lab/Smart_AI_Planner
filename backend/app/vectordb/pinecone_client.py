"""
Pinecone Vector Database Client
Updated for 384-dimensional embeddings from Hugging Face
"""
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Any, Optional
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class PineconeClient:
    """
    Pinecone client for storing and retrieving task embeddings.
    """

    def __init__(self):
        """Initialize Pinecone client and connect to index."""
        self.pc = None
        self.index = None

        try:
            if not settings.pinecone_api_key:
                logger.warning(" Pinecone API key not set. Vector search disabled.")
                return

            self.pc = Pinecone(api_key=settings.pinecone_api_key)
            self.index_name = settings.pinecone_index_name

            # Check if index exists, create if not
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]

            if self.index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {self.index_name}")
                self.pc.create_index(
                    name=self.index_name,
                    dimension=384,  # UPDATED: Hugging Face all-MiniLM-L6-v2 uses 384 dimensions
                    metric='cosine',
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )
                logger.info(f" Created index: {self.index_name}")

            self.index = self.pc.Index(self.index_name)
            logger.info(f" Connected to Pinecone index: {self.index_name}")

        except Exception as e:
            logger.error(f" Pinecone initialization failed: {e}")
            self.pc = None
            self.index = None

    async def upsert_task(
        self,
        task_id: str,
        embedding: List[float],
        metadata: Dict[str, Any]
    ) -> bool:
        """Store a task embedding in Pinecone."""
        if not self.pc or not self.index:
            logger.warning(" Pinecone not initialized, skipping upsert")
            return False

        try:
            # Validate embedding dimension
            if len(embedding) != 384:
                logger.warning(f" Embedding dimension {len(embedding)} != 384, skipping upsert")
                return False

            vector = {
                'id': f"task_{task_id}",
                'values': embedding,
                'metadata': metadata
            }

            self.index.upsert(vectors=[vector])
            logger.info(f" Stored embedding for task {task_id}")
            return True

        except Exception as e:
            logger.error(f" Failed to upsert task {task_id}: {e}")
            return False

    async def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar tasks based on embedding."""
        if not self.pc or not self.index:
            logger.warning(" Pinecone not initialized, skipping search")
            return []

        try:
            # Validate query dimension
            if len(query_embedding) != 384:
                logger.warning(f" Query embedding dimension {len(query_embedding)} != 384, skipping search")
                return []

            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                filter=filter_dict
            )

            similar_tasks = []
            for match in results.matches:
                similar_tasks.append({
                    'task_id': match.id.replace('task_', ''),
                    'score': match.score,
                    'metadata': match.metadata
                })

            logger.info(f" Found {len(similar_tasks)} similar tasks")
            return similar_tasks

        except Exception as e:
            logger.error(f" Search failed: {e}")
            return []

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task embedding from Pinecone."""
        if not self.pc or not self.index:
            logger.warning(" Pinecone not initialized, skipping deletion")
            return False

        try:
            self.index.delete(ids=[f"task_{task_id}"])
            logger.info(f" Deleted embedding for task {task_id}")
            return True
        except Exception as e:
            logger.error(f" Failed to delete task {task_id}: {e}")
            return False

    async def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        if not self.pc or not self.index:
            logger.warning(" Pinecone not initialized, no stats available")
            return {}

        try:
            stats = self.index.describe_index_stats()
            return {
                'total_vectors': stats.total_vector_count,
                'dimension': stats.dimension,
                'index_fullness': stats.index_fullness
            }
        except Exception as e:
            logger.error(f" Failed to get stats: {e}")
            return {}


# Singleton instance
_pinecone_client: Optional[PineconeClient] = None


def get_pinecone_client() -> PineconeClient:
    """Get or create Pinecone client singleton."""
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = PineconeClient()
    return _pinecone_client