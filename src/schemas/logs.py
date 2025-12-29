"""
Log Schemas
Phase 5 & 6: End-to-End Logging
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from uuid import UUID


class LogEvent(BaseModel):
    """Single event in the call log"""
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict = Field(default_factory=dict)


class CallLogPacket(BaseModel):
    """
    Complete call log packet structure
    From Phase 5 & 6, Task 6.1
    
    Example:
    {
        "call_id": "call_12345",
        "input_audio_url": "s3://...",
        "transcribed_text": "Send Crocin",
        "intent_detected": "ORDER_MEDICINE",
        "wallet_status": "APPROVED",
        "execution_status": "SUCCESS"
    }
    """
    call_id: str
    user_id: Optional[str] = None  # Internal ID only, not PII
    phone_number: Optional[str] = None  # Will be masked in logs
    
    # Audio
    input_audio_url: Optional[str] = None
    
    # Transcription
    transcribed_text: Optional[str] = None
    transcription_confidence: Optional[float] = None
    
    # Intent
    intent_detected: Optional[str] = None
    intent_confidence: Optional[float] = None
    parsed_intent: Optional[dict] = None
    
    # Wallet
    wallet_status: Optional[str] = None  # "APPROVED", "DENIED", "INSUFFICIENT"
    
    # Execution
    execution_status: Optional[str] = None  # "SUCCESS", "FAILED", "REFUNDED"
    order_id: Optional[str] = None
    
    # Timing
    call_started_at: Optional[datetime] = None
    call_ended_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    
    # Event stream
    events: List[LogEvent] = Field(default_factory=list)
    
    # Error tracking
    error_message: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def add_event(self, event_type: str, data: dict = None):
        """Add event to the log stream"""
        self.events.append(LogEvent(
            event_type=event_type,
            data=data or {}
        ))
    
    def to_db_dict(self) -> dict:
        """Convert to dict for database storage"""
        return {
            "call_id": self.call_id,
            "user_id": self.user_id,
            "input_audio_url": self.input_audio_url,
            "transcribed_text": self.transcribed_text,
            "transcription_confidence": self.transcription_confidence,
            "intent_detected": self.intent_detected,
            "intent_confidence": self.intent_confidence,
            "parsed_intent": self.parsed_intent,
            "wallet_status": self.wallet_status,
            "execution_status": self.execution_status,
            "call_started_at": self.call_started_at,
            "call_ended_at": self.call_ended_at,
            "duration_seconds": self.duration_seconds,
            "events": [e.dict() for e in self.events],
            "error_message": self.error_message
        }