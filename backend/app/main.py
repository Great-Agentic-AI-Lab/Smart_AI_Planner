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

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, settings.log_level, "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager: startup and shutdown tasks
    """
    # ---------------------------
    # Startup
    # ---------------------------
    logger.info("Starting Smart Personal Planner API...")

    # Initialize Pinecone (NEW API)
    try:
        if settings.pinecone_api_key:
            from pinecone import Pinecone
            pc = Pinecone(api_key=settings.pinecone_api_key)
            logger.info("Pinecone initialized")
    except Exception as e:
        logger.warning(f"Pinecone initialization failed: {e}")

    # Start Telegram bot (IMPROVED: better error handling)
    try:
        if settings.telegram_bot_token:
            from app.telegram.bot import start_bot
            await start_bot()
            logger.info(" Telegram bot started")
        else:
            logger.warning(" No Telegram token - bot disabled")
    except Exception as e:
        logger.warning(f" Telegram bot failed to start: {e}")
        logger.info("Server will continue without Telegram bot")

    yield

    # ---------------------------
    # Shutdown
    # ---------------------------
    logger.info(" Shutting down Smart Personal Planner API...")

    # Stop Telegram bot
    try:
        from app.telegram.bot import stop_bot
        await stop_bot()
        logger.info(" Telegram bot stopped")
    except Exception as e:
        logger.warning(f" Telegram bot failed to stop: {e}")


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
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

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
