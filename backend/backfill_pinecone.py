"""
Backfill Script
Populates Pinecone with embeddings for existing tasks.
Run this once after installing Vector DB.
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Task
from app.vectordb.task_hooks import on_task_created


async def backfill_embeddings():
    """Add embeddings for all existing tasks to Pinecone."""
    print(" Starting Pinecone backfill...")
    
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        print(f" Found {len(tasks)} tasks in database")
        
        success_count = 0
        for i, task in enumerate(tasks, 1):
            print(f"[{i}/{len(tasks)}] Processing: {task.title[:50]}...")
            
            try:
                result = await on_task_created(task)
                if result:
                    success_count += 1
                    print(f"   Stored embedding for task {task.id}")
                else:
                    print(f"   Failed to store embedding for task {task.id}")
            except Exception as e:
                print(f"   Error: {e}")
        
        print(f"\n Backfill complete!")
        print(f" Success: {success_count}/{len(tasks)} tasks")
        
    except Exception as e:
        print(f" Backfill failed: {e}")
        raise
    finally:
        db.close()


async def check_pinecone_stats():
    """Check Pinecone stats after backfill."""
    print("\n Checking Pinecone stats...")
    
    try:
        from app.vectordb import get_pinecone_client
        
        client = get_pinecone_client()
        stats = await client.get_stats()
        
        print(f"\n Pinecone Stats:")
        print(f"  Total vectors: {stats.get('total_vectors', 0)}")
        print(f"  Dimension: {stats.get('dimension', 0)}")
        print(f"  Index fullness: {stats.get('index_fullness', 0):.4f}")
        
    except Exception as e:
        print(f" Could not check stats: {e}")


async def main():
    """Main execution."""
    await backfill_embeddings()
    await check_pinecone_stats()


if __name__ == "__main__":
    print("=" * 60)
    print("PINECONE BACKFILL SCRIPT")
    print("=" * 60)
    
    asyncio.run(main())
    
    print("\n" + "=" * 60)
    print("DONE! Your tasks are now in Pinecone.")
    print("=" * 60)
