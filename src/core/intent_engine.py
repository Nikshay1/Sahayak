"""
Intent Parsing Engine
Phase 2: Task 2.2 - Convert transcript to strict JSON command
The LLM is used as a "Translation Layer," not a "Knowledge Base"
"""

import json
from typing import Optional, List
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from src.config.settings import settings
from src.config.constants import IntentType, UrgencyLevel
import logging

logger = logging.getLogger(__name__)


class IntentSchema(BaseModel):
    """
    Target Schema for deterministic intent extraction
    From Phase 2, Task 2.2
    """
    intent_type: str = Field(
        description="One of: ORDER_MEDICINE, CHECK_BALANCE, ORDER_STATUS, UNKNOWN"
    )
    items: List[str] = Field(
        default_factory=list,
        description="List of medicine names mentioned, e.g., ['Metformin 500mg']"
    )
    quantity: Optional[int] = Field(
        default=None,
        description="Number of units/strips requested"
    )
    confidence_score: float = Field(
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
    """
    Deterministic Intent Parser
    Uses GPT-4o for superior reasoning and intent extraction
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.OPENAI_MODEL
        
    async def parse_intent(
        self, 
        transcript: str, 
        user_context: dict = None
    ) -> IntentSchema:
        """
        Convert fuzzy speech transcript to structured intent
        
        Args:
            transcript: The transcribed user speech
            user_context: Optional context (medicine history, etc.)
                         Uses internal_id, NOT PII
        """
        
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(transcript, user_context)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,  # Low temperature for consistency
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            intent = IntentSchema(**result)
            
            logger.info(f"Parsed intent: {intent.intent_type} with confidence {intent.confidence_score}")
            
            return intent
            
        except Exception as e:
            logger.error(f"Intent parsing failed: {e}")
            return IntentSchema(
                intent_type=IntentType.UNKNOWN,
                confidence_score=0.0,
                clarification_needed="System error during intent parsing"
            )
    
    def _build_system_prompt(self) -> str:
        return """You are an intent parser for Sahayak, a voice assistant helping elderly users in India order medicines.

Your ONLY job is to convert spoken transcripts into a strict JSON structure. You are a Translation Layer, NOT a Knowledge Base.

RULES:
1. Only detect these intents: ORDER_MEDICINE, CHECK_BALANCE, ORDER_STATUS, UNKNOWN
2. If the user mentions emergency, injury, chest pain, or asks to call 911/112 -> Still output UNKNOWN but note "emergency_detected": true
3. If the user is just chatting or asking unrelated questions -> UNKNOWN
4. Be generous with medicine name matching - elderly users say things like:
   - "heart medicine" might mean Atorvastatin
   - "sugar ki goli" might mean Metformin
   - "BP tablet" might mean Amlodipine
   - "calcium wali" might mean Shelcal
5. Set confidence_score based on how clear the request is
6. If something is unclear, specify what needs clarification

OUTPUT FORMAT (strict JSON):
{
    "intent_type": "ORDER_MEDICINE|CHECK_BALANCE|ORDER_STATUS|UNKNOWN",
    "items": ["Medicine Name"],
    "quantity": 1,
    "confidence_score": 0.85,
    "urgency": "standard|immediate",
    "clarification_needed": null or "what needs to be asked",
    "raw_entities": {}
}"""

    def _build_user_prompt(self, transcript: str, user_context: dict = None) -> str:
        prompt = f"TRANSCRIPT: \"{transcript}\"\n\n"
        
        if user_context:
            prompt += "USER CONTEXT:\n"
            if user_context.get("medicine_history"):
                prompt += f"- Previously ordered medicines: {user_context['medicine_history']}\n"
            if user_context.get("internal_id"):
                prompt += f"- User ID: {user_context['internal_id']}\n"
        
        prompt += "\nParse this transcript into the JSON structure."
        
        return prompt
    
    def needs_clarification(self, intent: IntentSchema) -> bool:
        """Check if we need to ask for clarification"""
        return intent.confidence_score < settings.CONFIDENCE_THRESHOLD
    
    def should_refuse(self, intent: IntentSchema) -> bool:
        """Check if we should safely refuse (< 90% confidence)"""
        return intent.confidence_score < settings.SAFE_REFUSAL_THRESHOLD and \
               intent.intent_type == IntentType.UNKNOWN


class MedicineResolver:
    """
    Resolve fuzzy medicine names to actual SKUs
    Uses user's medicine history for context
    """
    
    def __init__(self, db_session):
        self.db = db_session
        
    async def resolve(
        self, 
        medicine_names: List[str], 
        user_id: str
    ) -> List[dict]:
        """
        Match spoken medicine names to catalog items
        
        Args:
            medicine_names: List of names from intent parser
            user_id: Internal user ID for history lookup
        
        Returns:
            List of matched medicines with SKU, price, etc.
        """
        resolved = []
        
        for name in medicine_names:
            # First check user's history
            match = await self._match_from_history(name, user_id)
            
            if not match:
                # Fall back to catalog search
                match = await self._match_from_catalog(name)
            
            if match:
                resolved.append(match)
            else:
                resolved.append({
                    "name": name,
                    "matched": False,
                    "needs_clarification": True
                })
        
        return resolved
    
    async def _match_from_history(self, name: str, user_id: str) -> Optional[dict]:
        """Check if this matches something user has ordered before"""
        # Implementation would query UserMedicineHistory
        # Checking medicine_name, generic_name, and user_aliases
        pass
    
    async def _match_from_catalog(self, name: str) -> Optional[dict]:
        """Fuzzy match against medicine catalog"""
        # Implementation would query MedicineCatalog
        # Using aliases and fuzzy string matching
        pass