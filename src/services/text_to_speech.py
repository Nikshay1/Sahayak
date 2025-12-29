"""
Text-to-Speech Service - gTTS VERSION (FREE!)
Uses Google's Text-to-Speech which is free for reasonable usage
"""

import io
from typing import Optional
from gtts import gTTS
from pydub import AudioSegment
import logging

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """
    Text-to-Speech using gTTS (FREE!)
    Generates natural-sounding voice
    """
    
    def __init__(self):
        pass  # No initialization needed for gTTS
        
    async def synthesize(
        self,
        text: str,
        language: str = "hi",  # Hindi default
        slow: bool = True,  # Slower speech for elderly
    ) -> bytes:
        """
        Convert text to speech
        
        Args:
            text: Text to speak
            language: Language code (hi=Hindi, en=English)
            slow: Slower speech (good for elderly)
            
        Returns:
            Audio bytes (MP3 format)
        """
        try:
            # Create gTTS object
            tts = gTTS(text=text, lang=language, slow=slow)
            
            # Save to bytes buffer
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            audio_bytes = audio_buffer.read()
            
            logger.info(f"Generated speech: '{text[:50]}...' ({len(audio_bytes)} bytes)")
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            raise
    
    async def synthesize_hindi(
        self,
        text: str,
        slow: bool = True
    ) -> bytes:
        """
        Synthesize Hindi/Hinglish text
        """
        return await self.synthesize(text=text, language="hi", slow=slow)
    
    async def synthesize_english(
        self,
        text: str,
        slow: bool = True
    ) -> bytes:
        """
        Synthesize English text (Indian accent)
        """
        # Use 'en-in' for Indian English accent
        try:
            tts = gTTS(text=text, lang="en", tld="co.in", slow=slow)
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            return audio_buffer.read()
        except Exception as e:
            logger.error(f"English TTS failed: {e}")
            # Fallback to regular English
            return await self.synthesize(text=text, language="en", slow=slow)


class VoiceResponseBuilder:
    """
    Build appropriate voice responses for different scenarios
    """
    
    def __init__(self, tts_service: TextToSpeechService = None):
        self.tts = tts_service or TextToSpeechService()
        
    async def build_greeting(self, user_name: str) -> bytes:
        """Generate personalized greeting"""
        text = f"Namaste {user_name}. Haan, main yahan hoon. Aaj main aapki kya madad kar sakti hoon?"
        return await self.tts.synthesize_hindi(text)
    
    async def build_confirmation(
        self,
        medicine_name: str,
        quantity: int,
        price: int,
        address: str
    ) -> bytes:
        """Generate order confirmation prompt"""
        text = (
            f"Main dekh sakti hoon ki aap aksar {medicine_name} order karti hain. "
            f"{quantity} ki strip {price} rupaye ki hai. "
            f"Kya main ise aapke ghar {address} mein order kar doon?"
        )
        return await self.tts.synthesize_hindi(text)
    
    async def build_completion(
        self,
        amount: int,
        balance: int,
        delivery_time: str
    ) -> bytes:
        """Generate order completion message"""
        text = (
            f"Ho gaya. Maine aapke wallet se {amount} rupaye pay kar diye hain. "
            f"Aapka naya balance {balance} rupaye hai. "
            f"Chemist {delivery_time} tak deliver kar dega."
        )
        return await self.tts.synthesize_hindi(text)
    
    async def build_clarification(self, clarification_type: str) -> bytes:
        """Generate clarification request"""
        if clarification_type == "medicine_name":
            text = (
                "Maine suna ki aapko dawai chahiye, lekin naam clear nahi tha. "
                "Kya aap tablet ka naam dobara bata sakti hain?"
            )
        elif clarification_type == "quantity":
            text = "Aapko kitni strips chahiye?"
        else:
            text = (
                "Mujhe clear samajh nahi aaya. "
                "Kripya dhire se dobara boliye."
            )
        
        return await self.tts.synthesize_hindi(text)
    
    async def build_error(self, error_type: str) -> bytes:
        """Generate error messages"""
        if error_type == "insufficient_balance":
            text = (
                "Mujhe maaf kijiye, aapke wallet mein itne paise nahi hain. "
                "Kripya apne parivar ke sadasya se Sahayak wallet mein paise add karne ko kahiye."
            )
        elif error_type == "api_error":
            text = (
                "Mujhe abhi order dene mein dikkat ho rahi hai. "
                "Aapke paise safe hain. Kripya kuch minute baad try kariye."
            )
        else:
            text = (
                "Mujhe maaf kijiye, kuch gadbad ho gayi. "
                "Kripya dobara try kariye ya apne caregiver ko call kariye."
            )
        
        return await self.tts.synthesize_hindi(text)