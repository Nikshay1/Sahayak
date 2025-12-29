"""
Sahayak Configuration Settings
Phase 1: Foundational Setup - System Boundaries & Stack Locking
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
    DATABASE_URL: str = "postgresql://sahayak:password@localhost:5432/sahayak_db"
    
    # Telephony Provider (Twilio/Exotel/Bland AI)
    TELEPHONY_PROVIDER: str = "twilio"  # Options: twilio, exotel, bland
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # OpenAI (GPT-4o for intent, Whisper for STT)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"
    WHISPER_MODEL: str = "whisper-1"
    
    # Voice Processing
    SILENCE_THRESHOLD_SECONDS: float = 1.5  # Wait 1.5s before assuming user finished
    CONFIDENCE_THRESHOLD: float = 0.85  # Below this triggers clarification
    SAFE_REFUSAL_THRESHOLD: float = 0.90  # Below 90% = explicit refusal
    
    # Wallet Rules
    MAX_TRANSACTION_AMOUNT: int = 2000  # ₹2000 hard cap
    DEFAULT_CURRENCY: str = "INR"
    
    # Supported Actions (System Boundaries)
    SUPPORTED_INTENTS: list = ["ORDER_MEDICINE", "CHECK_BALANCE", "ORDER_STATUS"]
    UNSUPPORTED_INTENTS: list = ["EMERGENCY", "BANKING", "GENERAL_CHAT"]
    
    # WhatsApp/SMS Notifications
    WHATSAPP_ENABLED: bool = True
    SMS_ENABLED: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()