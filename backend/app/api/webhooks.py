"""
Telegram Bot Webhook Endpoints
Handles incoming updates from Telegram and provides a health check.
"""

from fastapi import APIRouter, Request, HTTPException
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/telegram", summary="Receive Telegram Bot Updates")
async def telegram_webhook(request: Request):
    """
    Webhook endpoint for receiving updates from the Telegram Bot API.

    Telegram sends updates (messages, commands, callbacks) to this endpoint
    when the bot is configured with setWebhook.

    Returns a simple acknowledgment to Telegram.
    """
    try:
        update = await request.json()
        logger.info(f"Received Telegram update: {update}")

        # TODO: Forward update to Telegram bot handler for processing
        # Example: await bot.process_update(update)

        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing Telegram webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to process Telegram update"
        )


@router.get("/telegram/health", summary="Telegram Webhook Health Check")
async def telegram_webhook_health():
    """
    Health check endpoint for Telegram webhook integration.

    Returns a simple JSON indicating the webhook is active.
    """
    return {"status": "webhook active"}
