"""
Speech-to-Text Service - SIMPLE VERSION
Uses Google Speech Recognition (FREE!)
No API key needed for basic usage!
"""

import io
import os
import tempfile
from typing import Optional
import speech_recognition as sr
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class SpeechToTextService:
    """
    Speech-to-Text using Google Speech Recognition (FREE!)
    Simple, works instantly, no complex setup!
    """
    
    def __init__(self):
        self.recognizer = sr.Recognizer()
        
    async def transcribe(
        self,
        audio_data: bytes,
        language_hint: str = "hi-IN",
        prompt_hint: Optional[str] = None
    ) -> dict:
        """
        Transcribe audio to text
        
        Args:
            audio_data: Raw audio bytes (WAV format works best)
            language_hint: Language code (hi-IN=Hindi, en-IN=Indian English)
            prompt_hint: Not used in this version
        
        Returns:
            Dict with text, confidence, language
        """
        try:
            # Write audio to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_file.write(audio_data)
                tmp_path = tmp_file.name
            
            try:
                # Load audio file
                with sr.AudioFile(tmp_path) as source:
                    audio = self.recognizer.record(source)
                
                # Try Google Speech Recognition (FREE!)
                try:
                    # First try Hindi
                    text = self.recognizer.recognize_google(
                        audio, 
                        language=language_hint
                    )
                    detected_language = language_hint
                    
                except sr.UnknownValueError:
                    # If Hindi fails, try English
                    try:
                        text = self.recognizer.recognize_google(
                            audio, 
                            language="en-IN"
                        )
                        detected_language = "en-IN"
                    except sr.UnknownValueError:
                        text = ""
                        detected_language = "unknown"
                
                logger.info(f"Transcribed: '{text}' (lang: {detected_language})")
                
                return {
                    "text": text,
                    "language": detected_language,
                    "confidence": 0.9 if text else 0.0,
                    "duration": 0,
                }
                
            finally:
                # Clean up temp file
                os.unlink(tmp_path)
            
        except sr.RequestError as e:
            logger.error(f"Google Speech API error: {e}")
            return {
                "text": "",
                "language": "unknown",
                "confidence": 0.0,
                "error": f"API error: {e}"
            }
            
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {
                "text": "",
                "language": "unknown",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def transcribe_sync(
        self,
        audio_data: bytes,
        language_hint: str = "hi-IN"
    ) -> dict:
        """
        Synchronous version of transcribe (for non-async contexts)
        """
        import asyncio
        return asyncio.run(self.transcribe(audio_data, language_hint))


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