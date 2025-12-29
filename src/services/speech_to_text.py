"""
Speech-to-Text Service
Uses OpenAI Whisper for best dialect/accent handling
Phase 2: Voice Intake
"""

import io
from typing import Optional
from openai import AsyncOpenAI
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """
    Speech-to-Text using OpenAI Whisper
    Best for Indian dialect and accent handling
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.WHISPER_MODEL
        
    async def transcribe(
        self,
        audio_data: bytes,
        language_hint: str = "hi",
        prompt_hint: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes
            language_hint: Expected language (hi=Hindi, en=English)
            prompt_hint: Optional prompt to guide transcription
                        (e.g., "medicine names like Shelcal, Atorvastatin")
        
        Returns:
            Dict with text, confidence, language
        """
        try:
            # Create file-like object from bytes
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"  # Whisper needs a filename
            
            # Build transcription request
            transcription_params = {
                "model": self.model,
                "file": audio_file,
                "response_format": "verbose_json",  # Get detailed response
            }
            
            # Add language hint if provided
            if language_hint:
                transcription_params["language"] = language_hint
            
            # Add prompt hint for better medicine name recognition
            if prompt_hint:
                transcription_params["prompt"] = prompt_hint
            else:
                # Default prompt for medicine context
                transcription_params["prompt"] = (
                    "This is a conversation about ordering medicines. "
                    "Common medicine names include: Shelcal, Atorvastatin, Metformin, "
                    "Amlodipine, Crocin, Pantoprazole, Thyronorm. "
                    "The speaker may use Hindi words like 'dawai', 'goli', 'tablet'."
                )
            
            response = await self.client.audio.transcriptions.create(
                **transcription_params
            )
            
            logger.info(f"Transcribed: '{response.text}' (lang: {response.language})")
            
            return {
                "text": response.text,
                "language": response.language,
                "duration": response.duration,
                "confidence": self._estimate_confidence(response),
                "segments": getattr(response, 'segments', [])
            }
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "language": "unknown",
                "duration": 0,
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _estimate_confidence(self, response) -> float:
        """
        Estimate confidence from Whisper response
        Whisper doesn't directly provide confidence, so we estimate
        """
        # If we have segments with confidence scores
        if hasattr(response, 'segments') and response.segments:
            confidences = []
            for segment in response.segments:
                if hasattr(segment, 'no_speech_prob'):
                    # Lower no_speech_prob = higher confidence
                    confidences.append(1 - segment.no_speech_prob)
            if confidences:
                return sum(confidences) / len(confidences)
        
        # Default to high confidence if transcription succeeded
        return 0.9 if response.text else 0.0


class TranscriptionEnhancer:
    """
    Post-processing for transcriptions
    Handles common elderly speech patterns
    """
    
    def __init__(self):
        # Common medicine aliases spoken by elderly
        self.medicine_aliases = {
            "heart medicine": ["Atorvastatin", "Ecosprin"],
            "heart ki dawai": ["Atorvastatin", "Ecosprin"],
            "bp tablet": ["Amlodipine", "Telmisartan"],
            "bp ki goli": ["Amlodipine", "Telmisartan"],
            "sugar ki dawai": ["Metformin", "Glimepiride"],
            "sugar tablet": ["Metformin", "Glimepiride"],
            "calcium": ["Shelcal", "Calcimax"],
            "calcium wali": ["Shelcal", "Calcimax"],
            "haddi ki dawai": ["Shelcal", "Calcimax"],
            "thyroid": ["Thyronorm", "Eltroxin"],
            "acidity": ["Pantoprazole", "Omeprazole"],
            "pet ki dawai": ["Pantoprazole", "Omeprazole"],
            "dard ki goli": ["Crocin", "Dolo"],
            "bukhar ki dawai": ["Crocin", "Dolo"],
        }
        
        # Common speech corrections
        self.corrections = {
            "shell cal": "shelcal",
            "shell call": "shelcal",
            "metro form in": "metformin",
            "a tor va stat in": "atorvastatin",
        }
    
    def enhance(self, text: str) -> str:
        """
        Enhance transcription for better intent parsing
        """
        text = text.lower().strip()
        
        # Apply corrections
        for wrong, correct in self.corrections.items():
            text = text.replace(wrong, correct)
        
        return text
    
    def extract_medicine_hints(self, text: str) -> list:
        """
        Extract potential medicine names from common aliases
        """
        text_lower = text.lower()
        hints = []
        
        for alias, medicines in self.medicine_aliases.items():
            if alias in text_lower:
                hints.extend(medicines)
        
        return list(set(hints))