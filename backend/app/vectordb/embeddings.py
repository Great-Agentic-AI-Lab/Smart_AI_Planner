"""
Embedding Generation using Hugging Face (FREE - No API key required)
Best free option: sentence-transformers
"""
from sentence_transformers import SentenceTransformer
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using Hugging Face SentenceTransformers."""

    def __init__(self):
        """Initialize embedding model."""
        try:
            # All-MiniLM-L6-v2 is lightweight and fast (384 dimensions)
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info(" Embedding generator initialized (Hugging Face - all-MiniLM-L6-v2)")
        except Exception as e:
            logger.error(f" Failed to initialize embedding model: {e}")
            self.model = None

    async def generate_task_embedding(
        self,
        title: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[float]:
        """Generate embedding for a task."""
        try:
            if not self.model:
                logger.warning(" Embedding model not initialized, returning zero vector (384 dimensions)")
                return [0.0] * 384

            text_parts = [title]
            if description:
                text_parts.append(description)
            if tags and len(tags) > 0:
                text_parts.append(f"Tags: {', '.join(tags)}")

            combined_text = " | ".join(text_parts)

            # Generate embedding
            embedding = self.model.encode(combined_text).tolist()
            logger.info(f" Generated embedding (dim: {len(embedding)})")
            return embedding

        except Exception as e:
            logger.error(f" Embedding generation failed: {e}")
            return [0.0] * 384

    async def generate_query_embedding(self, query: str) -> List[float]:
        """Generate embedding for search query."""
        try:
            if not self.model:
                logger.warning(" Embedding model not initialized, returning zero vector (384 dimensions)")
                return [0.0] * 384

            embedding = self.model.encode(query).tolist()
            return embedding
            
        except Exception as e:
            logger.error(f" Query embedding failed: {e}")
            return [0.0] * 384


_embedding_generator: Optional[EmbeddingGenerator] = None


def get_embedding_generator() -> EmbeddingGenerator:
    """Get or create Embedding Generator singleton."""
    global _embedding_generator
    if _embedding_generator is None:
        _embedding_generator = EmbeddingGenerator()
    return _embedding_generator