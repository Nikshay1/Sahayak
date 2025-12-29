"""
Speech-to-Text Service - LOCAL WHISPER VERSION
Uses faster-whisper for FREE local transcription!
No API costs! Works offline!
"""

import io
import os
import tempfile
from typing import Optional
from faster_whisper import WhisperModel
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Global model instance (loaded once)
_whisper_model = None


def get_whisper_model() -> WhisperModel:
    """
    Get or create the Whisper model (singleton pattern)
    Model is downloaded once and cached locally
    """
    global _whisper_model
    
    if _whisper_model is None:
        logger.info(f"Loading Whisper model: {settings.WHISPER_MODEL_SIZE}")
        logger.info(f"Device: {settings.WHISPER_DEVICE}, Compute: {settings.WHISPER_COMPUTE_TYPE}")
        
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE
        )
        
        logger.info("Whisper model loaded successfully!")
    
    return _whisper_model


class SpeechToTextService:
    """
    Speech-to-Text using faster-whisper (LOCAL & FREE!)
    Best for Indian dialect and accent handling
    """
    
    def __init__(self):
        self.model = get_whisper_model()
        
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
        
        Returns:
            Dict with text, confidence, language
        """
        try:
            # Write audio to temporary file (faster-whisper needs a file)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name
            
            try:
                # Build initial prompt for better medicine recognition
                initial_prompt = prompt_hint or (
                    "Medicines: Shelcal, Atorvastatin, Metformin, Crocin, "
                    "Thyronorm, Amlodipine. Hindi words: dawai, goli, tablet, "
                    "calcium, heart medicine, sugar ki goli, BP tablet."
                )
                
                # Transcribe
                segments, info = self.model.transcribe(
                    tmp_path,
                    language=language_hint if language_hint else None,
                    initial_prompt=initial_prompt,
                    beam_size=5,
                    best_of=5,
                    temperature=0.0,  # More deterministic
                    condition_on_previous_text=True,
                    vad_filter=True,  # Voice activity detection
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                        speech_pad_ms=400,
                    )
                )
                
                # Combine all segments
                full_text = ""
                total_confidence = 0.0
                segment_count = 0
                
                for segment in segments:
                    full_text += segment.text + " "
                    # Approximate confidence from no_speech_prob
                    segment_confidence = 1.0 - (segment.no_speech_prob or 0.0)
                    total_confidence += segment_confidence
                    segment_count += 1
                
                # Calculate average confidence
                avg_confidence = total_confidence / max(segment_count, 1)
                
                full_text = full_text.strip()
                
                logger.info(f"Transcribed: '{full_text}' (lang: {info.language}, conf: {avg_confidence:.2f})")
                
                return {
                    "text": full_text,
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "duration": info.duration,
                    "confidence": avg_confidence,
                }
                
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "language": "unknown",
                "duration": 0,
                "confidence": 0.0,
                "error": str(e)
            }


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
        """Enhance transcription for better intent parsing"""
        text = text.lower().strip()
        
        for wrong, correct in self.corrections.items():
            text = text.replace(wrong, correct)
        
        return text
    
    def extract_medicine_hints(self, text: str) -> list:
        """Extract potential medicine names from common aliases"""
        text_lower = text.lower()
        hints = []
        
        for alias, medicines in self.medicine_aliases.items():
            if alias in text_lower:
                hints.extend(medicines)
        
        return list(set(hints))