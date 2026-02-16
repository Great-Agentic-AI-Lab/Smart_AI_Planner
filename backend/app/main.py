"""
Main FastAPI application entry point.
Handles startup/shutdown, multi-agent orchestration, and API routing.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import init_db
from app.api import tasks, events, chat, webhooks

# ---------------------------
# LOGGING CONFIGURATION
# ---------------------------
logger = logging.getLogger(__name__)

# Configure logging with more detail
logging.basicConfig(
    level=getattr(logging, settings.log_level, "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Set specific loggers to INFO to see database logs
logging.getLogger("app.database").setLevel(logging.INFO)
logging.getLogger("app.telegram").setLevel(logging.INFO)
logging.getLogger("app.vectordb").setLevel(logging.INFO)
logging.getLogger("app.agents").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager: startup and shutdown tasks
    """
    # ---------------------------
    # Startup
    # ---------------------------
    logger.info("=" * 60)
    logger.info("Starting Smart Personal Planner API...")
    logger.info("=" * 60)

    # Initialize Database Tables
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialization complete")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise

    # Initialize Pinecone
    try:
        if settings.pinecone_api_key:
            from pinecone import Pinecone
            pc = Pinecone(api_key=settings.pinecone_api_key)
            logger.info("Pinecone initialized")
        else:
            logger.warning("Pinecone API key not configured")
    except Exception as e:
        logger.warning(f"Pinecone initialization failed: {e}")

    # Start Telegram bot
    try:
        if settings.telegram_bot_token:
            from app.telegram.bot import start_bot
            await start_bot()
            logger.info("Telegram bot started")
        else:
            logger.warning("No Telegram token - bot disabled")
    except Exception as e:
        logger.warning(f"Telegram bot failed to start: {e}")
        logger.info("Server will continue without Telegram bot")

    # Start Scheduler for birthday/festival wishes
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started (birthdays, festivals, reminders)")
    except Exception as e:
        logger.warning(f"Scheduler failed to start: {e}")

    logger.info("=" * 60)
    logger.info("Application startup complete!")
    logger.info("=" * 60)

    yield

    # ---------------------------
    # Shutdown
    # ---------------------------
    logger.info("=" * 60)
    logger.info("Shutting down Smart Personal Planner API...")
    logger.info("=" * 60)

    # Stop Telegram bot
    try:
        from app.telegram.bot import stop_bot
        await stop_bot()
        logger.info("Telegram bot stopped")
    except Exception as e:
        logger.warning(f"Telegram bot failed to stop: {e}")

    # Stop Scheduler
    try:
        from app.scheduler import stop_scheduler
        stop_scheduler()
        logger.info("Scheduler stopped")
    except Exception as e:
        logger.warning(f"Scheduler failed to stop: {e}")

    logger.info("=" * 60)
    logger.info("Application shutdown complete")
    logger.info("=" * 60)


# ---------------------------
# Create FastAPI app
# ---------------------------
app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Personal Planner & Assistant with Multi-Agent Orchestration",
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan
)

# ---------------------------
# CORS middleware
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update to frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Global Exception Handler
# ---------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again later."}
    )

# ---------------------------
# Health Check Endpoints
# ---------------------------
@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "status": "running",
        "app": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected"
    }

# ---------------------------
# API Routers
# ---------------------------
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

# ---------------------------
# Uvicorn Runner
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
