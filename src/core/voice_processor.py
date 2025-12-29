"""
Voice Input Service
Phase 2: Task 2.1 - Capture audio from phone line or WhatsApp
"""

import asyncio
from typing import Optional, AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import io

from src.services.speech_to_text import SpeechToTextService
from src.config.settings import settings
from src.utils.audio_buffer import AudioBuffer
import logging

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    """Result of voice transcription"""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    is_complete: bool


class VoiceProcessor:
    """
    Voice Input Service
    
    Key Requirements:
    - Buffer audio streams to avoid cutting off slow speakers (elderly)
    - Wait at least 1.5 seconds of silence before assuming user finished
    - Handle dialect/accent variations (using Whisper)
    """
    
    def __init__(self, stt_service: SpeechToTextService):
        self.stt = stt_service
        self.silence_threshold = settings.SILENCE_THRESHOLD_SECONDS
        
    async def process_audio_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        call_id: str
    ) -> TranscriptionResult:
        """
        Process streaming audio from telephony provider
        
        Args:
            audio_stream: Async generator yielding audio chunks
            call_id: For logging and correlation
            
        Returns:
            TranscriptionResult with text and confidence
        """
        buffer = AudioBuffer()
        silence_start: Optional[datetime] = None
        
        async for chunk in audio_stream:
            buffer.add_chunk(chunk)
            
            # Check for silence
            if buffer.is_silence(chunk):
                if silence_start is None:
                    silence_start = datetime.now()
                else:
                    silence_duration = (datetime.now() - silence_start).total_seconds()
                    if silence_duration >= self.silence_threshold:
                        logger.info(f"Call {call_id}: Detected {silence_duration}s silence, processing...")
                        break
            else:
                silence_start = None
        
        # Process buffered audio
        audio_data = buffer.get_audio()
        
        if not audio_data:
            return TranscriptionResult(
                text="",
                confidence=0.0,
                language="unknown",
                duration_seconds=0.0,
                is_complete=False
            )
        
        # Transcribe using Whisper
        result = await self.stt.transcribe(
            audio_data=audio_data,
            language_hint="hi"  # Hindi hint for Indian context
        )
        
        return TranscriptionResult(
            text=result["text"],
            confidence=result.get("confidence", 0.9),
            language=result.get("language", "hi"),
            duration_seconds=buffer.duration_seconds,
            is_complete=True
        )
    
    async def process_audio_file(
        self,
        audio_url: str,
        call_id: str
    ) -> TranscriptionResult:
        """
        Process audio file (e.g., WhatsApp voice note)
        
        Args:
            audio_url: URL to audio file
            call_id: For logging
        """
        # Download audio
        audio_data = await self._download_audio(audio_url)
        
        # Transcribe
        result = await self.stt.transcribe(
            audio_data=audio_data,
            language_hint="hi"
        )
        
        return TranscriptionResult(
            text=result["text"],
            confidence=result.get("confidence", 0.9),
            language=result.get("language", "hi"),
            duration_seconds=result.get("duration", 0),
            is_complete=True
        )
    
    async def _download_audio(self, url: str) -> bytes:
        """Download audio from URL"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.read()


class ClarificationFlow:
    """
    Phase 2: Task 2.3 - Voice Clarification Flow
    
    Context: If confidence score < 0.85, loop back
    Strategy: Use polite, respectful language
    
    Bad: "Input invalid. Repeat."
    Good: "I heard you want medicine, but the name wasn't clear. 
           Could you say the name of the tablet again?"
    """
    
    def __init__(self, voice_processor: VoiceProcessor, max_attempts: int = 3):
        self.voice_processor = voice_processor
        self.max_attempts = max_attempts
        
    async def clarify(
        self,
        clarification_type: str,
        context: dict,
        audio_stream: AsyncGenerator[bytes, None],
        call_id: str
    ) -> Optional[str]:
        """
        Request and process clarification from user
        
        Args:
            clarification_type: What needs clarification (medicine_name, quantity, etc.)
            context: What we already know
            audio_stream: Incoming audio
            call_id: For logging
            
        Returns:
            Clarified value or None if max attempts exceeded
        """
        attempt = 0
        
        while attempt < self.max_attempts:
            result = await self.voice_processor.process_audio_stream(
                audio_stream, call_id
            )
            
            if result.confidence >= settings.CONFIDENCE_THRESHOLD:
                return result.text
            
            attempt += 1
            logger.info(f"Clarification attempt {attempt}/{self.max_attempts} for {call_id}")
        
        return None