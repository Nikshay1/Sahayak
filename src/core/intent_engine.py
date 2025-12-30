"""
Intent Parsing Engine - Using NEW google-genai package
For Gemini 2.5 Flash
"""

import json
from typing import Optional, List
from pydantic import BaseModel, Field
from google import genai
from src.config.settings import settings
from src.config.constants import IntentType, UrgencyLevel
import logging

logger = logging.getLogger(__name__)


class IntentSchema(BaseModel):
    """Target Schema for deterministic intent extraction"""
    intent_type: str = Field(
        default="UNKNOWN",
        description="One of: ORDER_MEDICINE, CHECK_BALANCE, ORDER_STATUS, UNKNOWN"
    )
    items: List[str] = Field(
        default_factory=list,
        description="List of medicine names mentioned"
    )
    quantity: Optional[int] = Field(
        default=None,
        description="Number of units/strips requested"
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0, le=1.0,
        description="Model's confidence in the interpretation"
    )
    urgency: str = Field(
        default=UrgencyLevel.STANDARD,
        description="'standard' or 'immediate'"
    )
    clarification_needed: Optional[str] = Field(
        default=None,
        description="What needs clarification if confidence is low"
    )
    raw_entities: dict = Field(
        default_factory=dict,
        description="Any other extracted entities"
    )


class IntentEngine:
    """Deterministic Intent Parser using Google Gemini 2.5 (NEW API)"""
    
    def __init__(self):
        self.client = None
        self._initialized = False
        self._init_error = None
        
    def _initialize(self):
        """Initialize Gemini Client - called lazily"""
        if self._initialized:
            return
            
        try:
            api_key = settings.GEMINI_API_KEY
            model_name = settings.GEMINI_MODEL
            
            logger.info(f"Initializing Gemini with model: {model_name}")
            
            if not api_key or api_key == "" or "your" in api_key.lower():
                self._init_error = "GEMINI_API_KEY is not set properly in .env file!"
                logger.error(self._init_error)
                return
            
            # NEW API: Create client with api_key
            self.client = genai.Client(api_key=api_key)
            
            self._initialized = True
            logger.info(f"Gemini client initialized successfully!")
            
        except Exception as e:
            self._init_error = f"Failed to initialize Gemini: {str(e)}"
            logger.error(self._init_error)
        
    async def parse_intent(
        self, 
        transcript: str, 
        user_context: dict = None
    ) -> IntentSchema:
        """Convert fuzzy speech transcript to structured intent"""
        
        # Initialize if not done
        self._initialize()
        
        # Check for initialization errors
        if self._init_error:
            logger.error(f"Gemini not initialized: {self._init_error}")
            return IntentSchema(
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                clarification_needed=f"AI Error: {self._init_error}"
            )
        
        if not self.client:
            return IntentSchema(
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                clarification_needed="AI client not available"
            )
        
        prompt = self._build_prompt(transcript, user_context)
        
        try:
            model_name = settings.GEMINI_MODEL
            logger.info(f"Sending to Gemini ({model_name}): '{transcript}'")
            
            # NEW API: Use client.models.generate_content()
            response = self.client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={
                    "temperature": 0.1,
                    "max_output_tokens": 1024,
                }
            )
            
            # Get response text
            result_text = response.text.strip()
            logger.info(f"Gemini raw response: {result_text[:500]}")
            
            # Clean up JSON (remove markdown code blocks if present)
            cleaned_text = result_text
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1]
            if "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[0]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            result = json.loads(cleaned_text)
            intent = IntentSchema(**result)
            
            logger.info(f"Parsed intent: {intent.intent_type} (confidence: {intent.confidence_score})")
            
            return intent
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Raw response was: {result_text if 'result_text' in dir() else 'None'}")
            return IntentSchema(
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                clarification_needed="Failed to parse AI response as JSON"
            )
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gemini API error: {error_msg}")
            
            # Check for common errors
            if "429" in error_msg or "quota" in error_msg.lower() or "rate" in error_msg.lower():
                clarification = "API rate limit exceeded. Please wait 1 minute and try again."
            elif "API_KEY" in error_msg.upper() or "invalid" in error_msg.lower() or "authenticate" in error_msg.lower():
                clarification = "Invalid API key. Please check your GEMINI_API_KEY."
            elif "not found" in error_msg.lower() or "model" in error_msg.lower():
                clarification = f"Model '{settings.GEMINI_MODEL}' not available. Try 'gemini-2.0-flash'."
            else:
                clarification = f"AI error: {error_msg[:100]}"
            
            return IntentSchema(
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                clarification_needed=clarification
            )
    
    def _build_prompt(self, transcript: str, user_context: dict = None) -> str:
        """Build the prompt for Gemini"""
        
        prompt = """You are an intent parser for Sahayak, a voice assistant helping elderly users in India order medicines.

Convert the spoken transcript into a JSON structure.

RULES:
1. Only these intents: ORDER_MEDICINE, CHECK_BALANCE, ORDER_STATUS, UNKNOWN
2. Be generous with medicine name matching:
   - "heart medicine" / "dil ki dawai" = Atorvastatin
   - "sugar ki goli" / "sugar ki dawai" = Metformin  
   - "BP tablet" / "BP ki goli" = Amlodipine
   - "calcium" / "calcium wali" / "haddi ki dawai" = Shelcal
   - "fever" / "bukhar ki dawai" / "dard ki goli" = Crocin
   - "thyroid" / "thyroid ki dawai" = Thyronorm
3. Set confidence_score between 0.0 and 1.0 based on how clear the request is
4. If emergency/chest pain/injury mentioned, set raw_entities.emergency_detected = true

"""
        
        if user_context and user_context.get("medicine_history"):
            prompt += f"User's previous medicines: {user_context['medicine_history']}\n\n"
        
        prompt += f"""TRANSCRIPT: "{transcript}"

Respond with ONLY this JSON format (no other text, no markdown, no explanation):
{{"intent_type": "ORDER_MEDICINE", "items": ["Shelcal 500"], "quantity": 1, "confidence_score": 0.9, "urgency": "standard", "clarification_needed": null, "raw_entities": {{}}}}

JSON:"""

        return prompt
    
    def needs_clarification(self, intent: IntentSchema) -> bool:
        """Check if we need to ask for clarification"""
        return intent.confidence_score < settings.CONFIDENCE_THRESHOLD
    
    def should_refuse(self, intent: IntentSchema) -> bool:
        """Check if we should safely refuse"""
        return intent.confidence_score < settings.SAFE_REFUSAL_THRESHOLD and \
               intent.intent_type == IntentType.UNKNOWN


class MedicineResolver:
    """Resolve fuzzy medicine names to actual SKUs"""
    
    def __init__(self, db_session=None):
        self.db = db_session
        
    async def resolve(self, medicine_names: List[str], user_id: str) -> List[dict]:
        """Match spoken medicine names to catalog items"""
        resolved = []
        
        medicine_map = {
            "shelcal": {"name": "Shelcal 500", "sku": "SHELCAL500", "price": 12000},
            "calcium": {"name": "Shelcal 500", "sku": "SHELCAL500", "price": 12000},
            "atorvastatin": {"name": "Atorvastatin 10mg", "sku": "ATORVA10", "price": 8500},
            "heart": {"name": "Atorvastatin 10mg", "sku": "ATORVA10", "price": 8500},
            "metformin": {"name": "Metformin 500mg", "sku": "METFORM500", "price": 4500},
            "sugar": {"name": "Metformin 500mg", "sku": "METFORM500", "price": 4500},
            "crocin": {"name": "Crocin 500mg", "sku": "CROCIN500", "price": 2500},
            "fever": {"name": "Crocin 500mg", "sku": "CROCIN500", "price": 2500},
            "thyronorm": {"name": "Thyronorm 50mcg", "sku": "THYRONORM50", "price": 11000},
            "thyroid": {"name": "Thyronorm 50mcg", "sku": "THYRONORM50", "price": 11000},
        }
        
        for name in medicine_names:
            name_lower = name.lower()
            matched = False
            
            for key, medicine in medicine_map.items():
                if key in name_lower:
                    resolved.append({**medicine, "matched": True})
                    matched = True
                    break
            
            if not matched:
                resolved.append({"name": name, "matched": False, "needs_clarification": True})
        
        return resolved