"""
Twilio Webhook Handlers
Phase 2: Voice-First Intake
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.request_validator import RequestValidator
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from src.db.database import get_db
from src.db.models import User, CallLog
from src.core.voice_processor import VoiceProcessor
from src.core.intent_engine import IntentEngine
from src.core.orchestrator import ExecutionOrchestrator
from src.services.speech_to_text import SpeechToTextService
from src.services.text_to_speech import TextToSpeechService
from src.config.settings import settings
from src.utils.privacy import PIIRedactor
from src.schemas.logs import CallLogPacket

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/twilio", tags=["telephony"])


class TwilioWebhookHandler:
    """
    Handles incoming Twilio voice webhooks
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.voice_processor = VoiceProcessor(SpeechToTextService())
        self.intent_engine = IntentEngine()
        self.pii_redactor = PIIRedactor()
        
    def validate_request(self, request: Request, signature: str) -> bool:
        """Validate Twilio webhook signature"""
        if settings.ENVIRONMENT == "development":
            return True  # Skip in dev
            
        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        return validator.validate(
            str(request.url),
            await request.form(),
            signature
        )


@router.post("/voice/incoming")
async def handle_incoming_call(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle incoming voice call
    This is the main entry point for phone calls
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    from_number = form_data.get("From")
    to_number = form_data.get("To")
    
    logger.info(f"Incoming call: {call_sid} from {from_number}")
    
    # Look up user by phone number
    user = await get_user_by_phone(db, from_number)
    
    # Create call log
    call_log = CallLogPacket(
        call_id=call_sid,
        user_id=str(user.id) if user else None,
        phone_number=from_number
    )
    call_log.add_event("CALL_STARTED", {"from": from_number, "to": to_number})
    
    # Build TwiML response
    response = VoiceResponse()
    
    if not user:
        # Unknown caller - politely redirect
        response.say(
            "I'm sorry, this number is not registered with Sahayak. "
            "Please contact your caregiver to set up your account.",
            voice="Polly.Aditi",  # Indian English voice
            language="en-IN"
        )
        response.hangup()
    else:
        # Greet the user
        greeting = f"Namaste {user.full_name.split()[0]}. Yes, I am here. How can I help you today?"
        
        # Use Gather to collect speech input
        gather = Gather(
            input="speech",
            action="/webhooks/twilio/voice/process",
            method="POST",
            language="hi-IN",  # Hindi
            speechTimeout=str(settings.SILENCE_THRESHOLD_SECONDS),  # Wait 1.5s
            speechModel="phone_call",
            enhanced=True,  # Better quality
            profanityFilter=False  # Don't filter - might affect medicine names
        )
        gather.say(greeting, voice="Polly.Aditi", language="hi-IN")
        
        response.append(gather)
        
        # If no input received
        response.say(
            "I didn't hear anything. Please call back if you need help.",
            voice="Polly.Aditi"
        )
    
    # Save call log
    await save_call_log(db, call_log)
    
    return Response(
        content=str(response),
        media_type="application/xml"
    )


@router.post("/voice/process")
async def process_voice_input(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Process speech input from user
    This is called after Gather completes
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    speech_result = form_data.get("SpeechResult", "")
    confidence = float(form_data.get("Confidence", 0))
    from_number = form_data.get("From")
    
    logger.info(f"Speech received: '{speech_result}' (confidence: {confidence})")
    
    # Get user and call log
    user = await get_user_by_phone(db, from_number)
    call_log = await get_call_log(db, call_sid)
    
    call_log.add_event("AUDIO_RECEIVED", {
        "speech_result": speech_result,
        "confidence": confidence
    })
    
    # Build user context (no PII sent to LLM)
    user_context = await build_user_context(db, user)
    
    # Parse intent
    intent = await IntentEngine().parse_intent(
        transcript=speech_result,
        user_context=user_context
    )
    
    call_log.add_event("INTENT_DETECTED", {
        "intent_type": intent.intent_type,
        "confidence": intent.confidence_score,
        "items": intent.items
    })
    
    # Get orchestrator
    orchestrator = await get_orchestrator(db)
    
    # Process intent
    result = await orchestrator.process_intent(
        intent=intent,
        user_id=user.id,
        user_context=user_context,
        call_log=call_log
    )
    
    # Build voice response
    response = VoiceResponse()
    
    if result.requires_confirmation:
        # Need to confirm with user
        gather = Gather(
            input="speech",
            action="/webhooks/twilio/voice/confirm",
            method="POST",
            language="hi-IN",
            speechTimeout="3",
            numDigits=1  # Also accept keypress
        )
        gather.say(result.voice_response, voice="Polly.Aditi", language="hi-IN")
        response.append(gather)
        
        # Store confirmation context in session
        await store_session_context(db, call_sid, result.confirmation_context)
    else:
        # Final response
        response.say(result.voice_response, voice="Polly.Aditi", language="hi-IN")
        
        # Ask if they need anything else
        gather = Gather(
            input="speech",
            action="/webhooks/twilio/voice/process",
            method="POST",
            language="hi-IN",
            speechTimeout="5"
        )
        gather.say(
            "Is there anything else I can help you with?",
            voice="Polly.Aditi"
        )
        response.append(gather)
        
        response.say("Thank you for using Sahayak. Goodbye!", voice="Polly.Aditi")
        response.hangup()
    
    # Save call log
    await save_call_log(db, call_log)
    
    return Response(content=str(response), media_type="application/xml")


@router.post("/voice/confirm")
async def handle_confirmation(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle user's confirmation response (Yes/No)
    Phase 4: Execute after confirmation
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    speech_result = form_data.get("SpeechResult", "").lower()
    digits = form_data.get("Digits", "")
    from_number = form_data.get("From")
    
    # Check for affirmative response
    affirmative_words = ["yes", "haan", "ha", "okay", "ok", "theek", "theek hai", "kar do", "order karo"]
    negative_words = ["no", "nahi", "naa", "cancel", "mat karo", "ruko"]
    
    is_confirmed = any(word in speech_result for word in affirmative_words) or digits == "1"
    is_cancelled = any(word in speech_result for word in negative_words) or digits == "2"
    
    response = VoiceResponse()
    
    if is_confirmed:
        # Get stored context and execute
        confirmation_context = await get_session_context(db, call_sid)
        
        if confirmation_context:
            user = await get_user_by_phone(db, from_number)
            call_log = await get_call_log(db, call_sid)
            orchestrator = await get_orchestrator(db)
            
            result = await orchestrator.execute_confirmed_order(
                confirmation_context=confirmation_context,
                call_log=call_log
            )
            
            response.say(result.voice_response, voice="Polly.Aditi", language="hi-IN")
        else:
            response.say(
                "I'm sorry, I couldn't find your order details. Please try again.",
                voice="Polly.Aditi"
            )
    
    elif is_cancelled:
        response.say(
            "Okay, I have cancelled the order. Is there anything else I can help with?",
            voice="Polly.Aditi"
        )
        
        gather = Gather(
            input="speech",
            action="/webhooks/twilio/voice/process",
            method="POST",
            language="hi-IN"
        )
        response.append(gather)
    
    else:
        # Didn't understand - ask again
        gather = Gather(
            input="speech",
            action="/webhooks/twilio/voice/confirm",
            method="POST",
            language="hi-IN"
        )
        gather.say(
            "I didn't understand. Please say 'yes' to confirm or 'no' to cancel.",
            voice="Polly.Aditi"
        )
        response.append(gather)
    
    response.say("Thank you for using Sahayak. Goodbye!", voice="Polly.Aditi")
    response.hangup()
    
    return Response(content=str(response), media_type="application/xml")


@router.post("/voice/status")
async def handle_call_status(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle call status callbacks (completed, failed, etc.)
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    duration = form_data.get("CallDuration")
    
    logger.info(f"Call {call_sid} status: {call_status}, duration: {duration}s")
    
    # Update call log
    call_log = await get_call_log(db, call_sid)
    if call_log:
        call_log.add_event("CALL_ENDED", {
            "status": call_status,
            "duration": duration
        })
        call_log.call_ended_at = datetime.now()
        call_log.duration_seconds = int(duration) if duration else 0
        await save_call_log(db, call_log)
    
    return {"status": "ok"}


# Helper functions
async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    """Look up user by phone number"""
    from sqlalchemy import select
    
    # Normalize phone number
    phone = phone.replace("+91", "").replace("+", "").strip()
    if len(phone) == 10:
        phone = f"+91{phone}"
    
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    return result.scalar_one_or_none()


async def build_user_context(db: AsyncSession, user: User) -> dict:
    """
    Build context for intent parsing
    Uses internal_id, NOT PII (Phase 6: Privacy Controls)
    """
    from sqlalchemy import select
    from src.db.models import UserMedicineHistory
    
    # Get medicine history
    result = await db.execute(
        select(UserMedicineHistory)
        .where(UserMedicineHistory.user_id == user.id)
        .order_by(UserMedicineHistory.last_ordered.desc())
        .limit(10)
    )
    history = result.scalars().all()
    
    medicine_history = [
        {
            "name": h.medicine_name,
            "aliases": h.user_aliases,
            "typical_quantity": h.typical_quantity
        }
        for h in history
    ]
    
    return {
        "internal_id": user.internal_id,  # Use internal ID, not name
        "medicine_history": medicine_history,
        "address": user.city,  # General location only
        "full_address": f"{user.address_line1}, {user.city} - {user.pincode}",
        "preferred_language": user.preferred_language
    }


async def get_orchestrator(db: AsyncSession) -> ExecutionOrchestrator:
    """Get configured orchestrator"""
    from src.adapters.pharmacy_adapter import get_pharmacy_adapter
    from src.services.notification_service import NotificationService
    from src.wallet.ledger import WalletLedger
    
    return ExecutionOrchestrator(
        db_session=db,
        intent_engine=IntentEngine(),
        wallet_ledger=WalletLedger(db),
        pharmacy_adapter=get_pharmacy_adapter(),
        notification_service=NotificationService()
    )


async def get_call_log(db: AsyncSession, call_sid: str) -> Optional[CallLogPacket]:
    """Retrieve call log"""
    # Implementation
    pass


async def save_call_log(db: AsyncSession, call_log: CallLogPacket):
    """Persist call log"""
    # Implementation
    pass


async def store_session_context(db: AsyncSession, call_sid: str, context: dict):
    """Store confirmation context for call session"""
    # Could use Redis for production
    pass


async def get_session_context(db: AsyncSession, call_sid: str) -> Optional[dict]:
    """Retrieve session context"""
    pass