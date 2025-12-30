"""
WhatsApp Webhook Handler
Simplified version for MVP
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
import logging

from src.db.database import get_db
from src.db.models import User
from src.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


@router.get("/verify")
async def verify_webhook(request: Request):
    """
    WhatsApp webhook verification
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = "sahayak_verify"
    
    if mode == "subscribe" and token == verify_token:
        return int(challenge) if challenge else 0
    
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/message")
async def handle_whatsapp_message(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming WhatsApp messages
    """
    try:
        body = await request.json()
        
        # Extract message data
        entry = body.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return {"status": "no_message"}
        
        message = messages[0]
        from_number = message.get("from", "unknown")
        message_type = message.get("type", "unknown")
        
        logger.info(f"WhatsApp message from {from_number}, type: {message_type}")
        
        # Get user
        user = await get_user_by_whatsapp(db, from_number)
        
        if not user:
            logger.info(f"Unregistered user: {from_number}")
            return {"status": "unregistered_user"}
        
        # Handle text message
        if message_type == "text":
            text = message.get("text", {}).get("body", "")
            logger.info(f"Text message from {from_number}: {text}")
            return {"status": "processed", "text": text}
        
        # Handle audio message
        elif message_type == "audio":
            logger.info(f"Audio message from {from_number}")
            return {"status": "audio_received"}
        
        return {"status": "unsupported_type", "type": message_type}
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return {"status": "error", "detail": str(e)}


async def get_user_by_whatsapp(db: AsyncSession, phone: str) -> Optional[User]:
    """Get user by WhatsApp number"""
    # Normalize phone
    phone_clean = phone.replace(" ", "").replace("-", "")
    if phone_clean.startswith("91"):
        phone_clean = f"+{phone_clean}"
    elif not phone_clean.startswith("+"):
        phone_clean = f"+91{phone_clean}"
    
    result = await db.execute(
        select(User).where(User.phone_number.contains(phone_clean[-10:]))
    )
    return result.scalar_one_or_none()