"""
Voice API Routes
For testing and debugging voice interactions
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import io

from src.db.database import get_db
from src.db.models import User
from src.core.intent_engine import IntentEngine
from src.services.speech_to_text import SpeechToTextService
from src.services.text_to_speech import TextToSpeechService
from sqlalchemy import select

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TranscribeResponse(BaseModel):
    """Response from transcription"""
    text: str
    language: str
    confidence: float
    duration: float


class IntentResponse(BaseModel):
    """Response from intent parsing"""
    intent_type: str
    items: list
    quantity: Optional[int]
    confidence_score: float
    urgency: str
    clarification_needed: Optional[str]


class TextToSpeechRequest(BaseModel):
    """Request for TTS"""
    text: str
    voice: str = "nova"
    speed: float = 0.9


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
):
    """
    Transcribe audio file to text
    Useful for testing the STT pipeline
    """
    # Read audio file
    audio_data = await file.read()
    
    # Transcribe
    stt = SpeechToTextService()
    result = await stt.transcribe(audio_data)
    
    return TranscribeResponse(
        text=result["text"],
        language=result.get("language", "unknown"),
        confidence=result.get("confidence", 0.0),
        duration=result.get("duration", 0.0)
    )


@router.post("/parse-intent", response_model=IntentResponse)
async def parse_intent(
    text: str,
    phone_number: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Parse intent from text
    Useful for testing the intent engine
    """
    user_context = None
    
    if phone_number:
        # Get user context
        phone = phone_number.replace(" ", "").replace("-", "")
        if not phone.startswith("+91"):
            phone = f"+91{phone[-10:]}"
        
        result = await db.execute(
            select(User).where(User.phone_number == phone)
        )
        user = result.scalar_one_or_none()
        
        if user:
            from src.db.models import UserMedicineHistory
            
            history_result = await db.execute(
                select(UserMedicineHistory)
                .where(UserMedicineHistory.user_id == user.id)
            )
            history = history_result.scalars().all()
            
            user_context = {
                "internal_id": user.internal_id,
                "medicine_history": [
                    {"name": h.medicine_name, "aliases": h.user_aliases}
                    for h in history
                ]
            }
    
    # Parse intent
    intent_engine = IntentEngine()
    intent = await intent_engine.parse_intent(text, user_context)
    
    return IntentResponse(
        intent_type=intent.intent_type,
        items=intent.items,
        quantity=intent.quantity,
        confidence_score=intent.confidence_score,
        urgency=intent.urgency,
        clarification_needed=intent.clarification_needed
    )


@router.post("/synthesize")
async def synthesize_speech(request: TextToSpeechRequest):
    """
    Convert text to speech
    Returns audio file
    """
    from fastapi.responses import Response
    
    tts = TextToSpeechService()
    audio_bytes = await tts.synthesize(
        text=request.text,
        voice=request.voice,
        speed=request.speed
    )
    
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={
            "Content-Disposition": f"attachment; filename=speech.mp3"
        }
    )


@router.post("/simulate-call")
async def simulate_call(
    phone_number: str,
    transcript: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Simulate a voice call for testing
    Takes a transcript and processes it through the full pipeline
    """
    from src.core.orchestrator import ExecutionOrchestrator
    from src.wallet.ledger import WalletLedger
    from src.adapters.pharmacy_adapter import MockPharmacyAdapter
    from src.services.notification_service import NotificationService
    from src.schemas.logs import CallLogPacket
    from uuid import uuid4
    
    # Get user
    phone = phone_number.replace(" ", "").replace("-", "")
    if not phone.startswith("+91"):
        phone = f"+91{phone[-10:]}"
    
    result = await db.execute(
        select(User).where(User.phone_number == phone)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build context
    from src.db.models import UserMedicineHistory
    
    history_result = await db.execute(
        select(UserMedicineHistory)
        .where(UserMedicineHistory.user_id == user.id)
    )
    history = history_result.scalars().all()
    
    user_context = {
        "internal_id": user.internal_id,
        "medicine_history": [
            {"name": h.medicine_name, "aliases": h.user_aliases}
            for h in history
        ],
        "address": user.city,
        "full_address": f"{user.address_line1}, {user.city} - {user.pincode}"
    }
    
    # Parse intent
    intent_engine = IntentEngine()
    intent = await intent_engine.parse_intent(transcript, user_context)
    
    # Create orchestrator
    orchestrator = ExecutionOrchestrator(
        db_session=db,
        intent_engine=intent_engine,
        wallet_ledger=WalletLedger(db),
        pharmacy_adapter=MockPharmacyAdapter(),
        notification_service=NotificationService()
    )
    
    # Create call log
    call_log = CallLogPacket(
        call_id=f"sim_{uuid4().hex[:8]}",
        user_id=user.internal_id
    )
    
    # Process
    result = await orchestrator.process_intent(
        intent=intent,
        user_id=user.id,
        user_context=user_context,
        call_log=call_log
    )
    
    return {
        "success": result.success,
        "voice_response": result.voice_response,
        "requires_confirmation": result.requires_confirmation,
        "intent_detected": intent.intent_type,
        "confidence": intent.confidence_score,
        "call_log_events": [e.dict() for e in call_log.events]
    }