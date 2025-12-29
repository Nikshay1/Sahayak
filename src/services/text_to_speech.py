"""
Text-to-Speech Service
For generating voice responses
"""

import io
from typing import Optional
from openai import AsyncOpenAI
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class TextToSpeechService:
    """
    Text-to-Speech using OpenAI TTS
    Generates natural-sounding voice for elderly users
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
    async def synthesize(
        self,
        text: str,
        voice: str = "alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
        speed: float = 0.9,  # Slightly slower for elderly
        response_format: str = "mp3"
    ) -> bytes:
        """
        Convert text to speech
        
        Args:
            text: Text to speak
            voice: Voice model to use
            speed: Speech speed (0.25 to 4.0), 0.9 is good for elderly
            response_format: Audio format (mp3, opus, aac, flac)
            
        Returns:
            Audio bytes
        """
        try:
            response = await self.client.audio.speech.create(
                model="tts-1",  # or "tts-1-hd" for higher quality
                voice=voice,
                input=text,
                speed=speed,
                response_format=response_format
            )
            
            # Get audio bytes
            audio_bytes = response.content
            
            logger.info(f"Generated speech for: '{text[:50]}...' ({len(audio_bytes)} bytes)")
            
            return audio_bytes
            
        except Exception as e:
            logger.error(f"TTS failed: {e}")
            raise
    
    async def synthesize_hindi(
        self,
        text: str,
        speed: float = 0.9
    ) -> bytes:
        """
        Synthesize Hindi/Hinglish text
        Uses voice that handles Hindi well
        """
        # Note: OpenAI TTS handles multiple languages
        # For production, consider dedicated Hindi TTS like Google Cloud TTS
        return await self.synthesize(
            text=text,
            voice="nova",  # Nova handles Hindi reasonably well
            speed=speed
        )


class VoiceResponseBuilder:
    """
    Build appropriate voice responses for different scenarios
    Ensures polite, elderly-friendly communication
    """
    
    def __init__(self, tts_service: TextToSpeechService):
        self.tts = tts_service
        
    async def build_greeting(self, user_name: str) -> bytes:
        """Generate personalized greeting"""
        text = f"Namaste {user_name}. Yes, I am here. How can I help you today?"
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
            f"I can see you usually order {medicine_name}. "
            f"A strip of {quantity} costs {price} rupees. "
            f"Shall I order it to your home in {address}?"
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
            f"Done. I have paid {amount} rupees from your wallet. "
            f"Your new balance is {balance} rupees. "
            f"The chemist will deliver it by {delivery_time}."
        )
        return await self.tts.synthesize_hindi(text)
    
    async def build_clarification(self, clarification_type: str) -> bytes:
        """Generate clarification request"""
        if clarification_type == "medicine_name":
            text = (
                "I heard you want medicine, but the name wasn't clear. "
                "Could you say the name of the tablet again?"
            )
        elif clarification_type == "quantity":
            text = "How many strips would you like?"
        else:
            text = (
                "I did not understand clearly. "
                "Please try saying it again slowly."
            )
        
        return await self.tts.synthesize_hindi(text)
    
    async def build_error(self, error_type: str) -> bytes:
        """Generate error messages"""
        if error_type == "insufficient_balance":
            text = (
                "I'm sorry, but your wallet balance is not enough for this order. "
                "Please ask your family member to add money to your Sahayak wallet."
            )
        elif error_type == "api_error":
            text = (
                "I'm having trouble placing your order right now. "
                "Your money is safe. Please try again in a few minutes."
            )
        else:
            text = (
                "I'm sorry, something went wrong. "
                "Please try again or call your caregiver for help."
            )
        
        return await self.tts.synthesize_hindi(text)