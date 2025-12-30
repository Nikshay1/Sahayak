"""
Twilio Webhook Handlers
Phase 2: Voice-First Intake
FIXED VERSION
"""

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from datetime import datetime
from uuid import uuid4
import logging

from src.db.database import get_db
from src.db.models import User, CallLog
from src.config.settings import settings
from src.config.constants import VoiceResponses, IntentType

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks/twilio", tags=["telephony"])


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
    
    call_sid = form_data.get("CallSid", "unknown")
    from_number = form_data.get("From", "unknown")
    to_number = form_data.get("To", "unknown")
    
    logger.info(f"Incoming call: {call_sid} from {from_number}")
    
    # Look up user by phone number
    user = await get_user_by_phone(db, from_number)
    
    # Build TwiML response (simple XML for Twilio)
    if not user:
        # Unknown caller
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="en-IN">
        I'm sorry, this number is not registered with Sahayak. 
        Please contact your caregiver to set up your account.
    </Say>
    <Hangup/>
</Response>"""
    else:
        # Greet the user and gather speech
        user_name = user.full_name.split()[0] if user.full_name else "there"
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/webhooks/twilio/voice/process" method="POST" 
            language="hi-IN" speechTimeout="2" enhanced="true">
        <Say voice="Polly.Aditi" language="hi-IN">
            Namaste {user_name}. Yes, I am here. How can I help you today?
        </Say>
    </Gather>
    <Say voice="Polly.Aditi">
        I didn't hear anything. Please call back if you need help.
    </Say>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/process")
async def process_voice_input(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Process speech input from user
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid", "unknown")
    speech_result = form_data.get("SpeechResult", "")
    confidence = float(form_data.get("Confidence", 0))
    from_number = form_data.get("From", "unknown")
    
    logger.info(f"Speech received: '{speech_result}' (confidence: {confidence})")
    
    # Get user
    user = await get_user_by_phone(db, from_number)
    
    if not user:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi">User not found. Goodbye.</Say>
    <Hangup/>
</Response>"""
        return Response(content=twiml, media_type="application/xml")
    
    # For now, echo back what was heard and ask for confirmation
    # In production, this would go through the intent engine
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/webhooks/twilio/voice/confirm" method="POST"
            language="hi-IN" speechTimeout="3">
        <Say voice="Polly.Aditi" language="hi-IN">
            I heard you say: {speech_result}. 
            Is this correct? Please say yes or no.
        </Say>
    </Gather>
    <Say voice="Polly.Aditi">
        I didn't hear your response. Please call back.
    </Say>
    <Hangup/>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/confirm")
async def handle_confirmation(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle user's confirmation response (Yes/No)
    """
    form_data = await request.form()
    
    speech_result = form_data.get("SpeechResult", "").lower()
    
    # Check for affirmative response
    affirmative_words = ["yes", "haan", "ha", "okay", "ok", "theek", "theek hai"]
    negative_words = ["no", "nahi", "naa", "cancel", "mat karo"]
    
    is_confirmed = any(word in speech_result for word in affirmative_words)
    is_cancelled = any(word in speech_result for word in negative_words)
    
    if is_confirmed:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        Great! Your request has been confirmed. Thank you for using Sahayak. Goodbye!
    </Say>
    <Hangup/>
</Response>"""
    elif is_cancelled:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Aditi" language="hi-IN">
        Okay, I have cancelled your request. Thank you for using Sahayak. Goodbye!
    </Say>
    <Hangup/>
</Response>"""
    else:
        twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather input="speech" action="/webhooks/twilio/voice/confirm" method="POST"
            language="hi-IN" speechTimeout="3">
        <Say voice="Polly.Aditi" language="hi-IN">
            I didn't understand. Please say yes to confirm or no to cancel.
        </Say>
    </Gather>
    <Say voice="Polly.Aditi">Goodbye!</Say>
    <Hangup/>
</Response>"""
    
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/status")
async def handle_call_status(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Handle call status callbacks
    """
    form_data = await request.form()
    
    call_sid = form_data.get("CallSid", "unknown")
    call_status = form_data.get("CallStatus", "unknown")
    duration = form_data.get("CallDuration", "0")
    
    logger.info(f"Call {call_sid} status: {call_status}, duration: {duration}s")
    
    return {"status": "ok"}


# Helper functions
async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    """Look up user by phone number"""
    # Normalize phone number
    phone_clean = phone.replace(" ", "").replace("-", "")
    
    # Try different formats
    phone_variants = [
        phone_clean,
        f"+91{phone_clean[-10:]}" if len(phone_clean) >= 10 else phone_clean,
        phone_clean[-10:] if len(phone_clean) >= 10 else phone_clean,
    ]
    
    for phone_variant in phone_variants:
        result = await db.execute(
            select(User).where(User.phone_number.contains(phone_variant[-10:]))
        )
        user = result.scalar_one_or_none()
        if user:
            return user
    
    return None