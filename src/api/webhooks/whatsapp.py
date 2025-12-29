"""
WhatsApp Webhook Handler
For voice notes sent via WhatsApp
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from src.db.database import get_db
from src.db.models import User
from src.core.voice_processor import VoiceProcessor
from src.core.intent_engine import IntentEngine
from src.services.speech_to_text import SpeechToTextService
from src.services.notification_service import NotificationService
from src.config.settings import settings
from sqlalchemy import select

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp"])


@router.get("/verify")
async def verify_webhook(request: Request):
    """
    WhatsApp webhook verification
    Required for setting up the webhook
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    verify_token = settings.WHATSAPP_VERIFY_TOKEN if hasattr(settings, 'WHATSAPP_VERIFY_TOKEN') else "sahayak_verify"
    
    if mode == "subscribe" and token == verify_token:
        return int(challenge)
    
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/message")
async def handle_whatsapp_message(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming WhatsApp messages (voice notes)
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
        from_number = message.get("from")
        message_type = message.get("type")
        
        logger.info(f"WhatsApp message from {from_number}, type: {message_type}")
        
        # Get user
        user = await get_user_by_whatsapp(db, from_number)
        
        if not user:
            # Send registration message
            await send_whatsapp_reply(
                from_number,
                "Namaste! This number is not registered with Sahayak. "
                "Please ask your caregiver to set up your account."
            )
            return {"status": "unregistered_user"}
        
        # Handle voice note
        if message_type == "audio":
            audio = message.get("audio", {})
            audio_id = audio.get("id")
            
            # Download and process audio
            audio_url = await get_whatsapp_media_url(audio_id)
            
            # Process voice
            voice_processor = VoiceProcessor(SpeechToTextService())
            transcription = await voice_processor.process_audio_file(
                audio_url=audio_url,
                call_id=f"wa_{message.get('id')}"
            )
            
            # Parse intent
            intent_engine = IntentEngine()
            user_context = await build_user_context(db, user)
            
            intent = await intent_engine.parse_intent(
                transcript=transcription.text,
                user_context=user_context
            )
            
            # For WhatsApp, we'll send a confirmation message
            # Full order execution would require additional confirmation flow
            response = build_whatsapp_response(intent, user)
            
            await send_whatsapp_reply(from_number, response)
            
            return {"status": "processed", "intent": intent.intent_type}
        
        # Handle text message
        elif message_type == "text":
            text = message.get("text", {}).get("body", "")
            
            # Parse intent from text
            intent_engine = IntentEngine()
            user_context = await build_user_context(db, user)
            
            intent = await intent_engine.parse_intent(
                transcript=text,
                user_context=user_context
            )
            
            response = build_whatsapp_response(intent, user)
            await send_whatsapp_reply(from_number, response)
            
            return {"status": "processed", "intent": intent.intent_type}
        
        return {"status": "unsupported_type"}
        
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}")
        return {"status": "error", "detail": str(e)}


async def get_user_by_whatsapp(db: AsyncSession, phone: str):
    """Get user by WhatsApp number"""
    # WhatsApp numbers come as country code + number (e.g., 919876543210)
    if phone.startswith("91"):
        phone = f"+{phone}"
    elif not phone.startswith("+"):
        phone = f"+91{phone}"
    
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    return result.scalar_one_or_none()


async def build_user_context(db: AsyncSession, user: User) -> dict:
    """Build user context for intent parsing"""
    from src.db.models import UserMedicineHistory
    
    result = await db.execute(
        select(UserMedicineHistory)
        .where(UserMedicineHistory.user_id == user.id)
    )
    history = result.scalars().all()
    
    return {
        "internal_id": user.internal_id,
        "medicine_history": [
            {"name": h.medicine_name, "aliases": h.user_aliases}
            for h in history
        ]
    }


def build_whatsapp_response(intent, user) -> str:
    """Build appropriate WhatsApp response"""
    from src.config.constants import IntentType
    
    if intent.intent_type == IntentType.ORDER_MEDICINE:
        if intent.items:
            return (
                f"🏥 Medicine Order Request\n\n"
                f"I understood you want: {', '.join(intent.items)}\n"
                f"Quantity: {intent.quantity or 1}\n\n"
                f"For orders, please call Sahayak directly for voice confirmation.\n"
                f"📞 Call now to complete your order."
            )
        else:
            return (
                "I understood you want to order medicine, but I couldn't identify which one.\n"
                "Please call Sahayak and say the medicine name clearly."
            )
    
    elif intent.intent_type == IntentType.CHECK_BALANCE:
        return (
            f"💰 Your Sahayak Wallet\n\n"
            f"Balance: ₹{user.current_balance // 100}\n"
            f"Available: ₹{(user.current_balance - user.locked_balance) // 100}\n\n"
            f"Call Sahayak to place an order."
        )
    
    else:
        return (
            "I'm not sure what you need. Please call Sahayak directly and I can help you:\n"
            "• Order medicines\n"
            "• Check your wallet balance\n\n"
            "📞 Call now for assistance."
        )


async def get_whatsapp_media_url(media_id: str) -> str:
    """Get download URL for WhatsApp media"""
    import httpx
    
    # This would use the WhatsApp Business API
    # Implementation depends on your WhatsApp setup
    url = f"https://graph.facebook.com/v17.0/{media_id}"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
        )
        data = response.json()
        return data.get("url")


async def send_whatsapp_reply(to_number: str, message: str):
    """Send WhatsApp reply message"""
    import httpx
    
    # Using WhatsApp Business API
    url = f"https://graph.facebook.com/v17.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json"
            }
        )