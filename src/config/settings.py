"""
Sahayak Configuration Settings
SIMPLE VERSION - Uses Google Speech Recognition
"""

from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Sahayak"
    APP_VERSION: str = "0.1.0-mvp"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Database (PostgreSQL for ACID compliance)
    DATABASE_URL: str = "postgresql://sahayak:sahayak_password@db:5432/sahayak_db"
    
    # Telephony Provider
    TELEPHONY_PROVIDER: str = "twilio"
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # ============== GEMINI CONFIG ==============
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"
    
    # ============== SPEECH CONFIG ==============
    # Using Google Speech Recognition (FREE!)
    SPEECH_LANGUAGE: str = "hi-IN"  # Hindi (India)
    
    # Voice Processing
    SILENCE_THRESHOLD_SECONDS: float = 1.5
    CONFIDENCE_THRESHOLD: float = 0.85
    SAFE_REFUSAL_THRESHOLD: float = 0.90
    
    # Wallet Rules
    MAX_TRANSACTION_AMOUNT: int = 2000
    DEFAULT_CURRENCY: str = "INR"
    
    # Supported Actions
    SUPPORTED_INTENTS: list = ["ORDER_MEDICINE", "CHECK_BALANCE", "ORDER_STATUS"]
    UNSUPPORTED_INTENTS: list = ["EMERGENCY", "BANKING", "GENERAL_CHAT"]
    
    # Notifications
    WHATSAPP_ENABLED: bool = False
    SMS_ENABLED: bool = False
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()