"""
Privacy Controls
Phase 6: Task 6.2 - PII Redaction
Do not send user's full name or phone number to LLM
"""

import re
from typing import Optional
import hashlib


class PIIRedactor:
    """
    Redacts Personally Identifiable Information before sending to LLM
    """
    
    def __init__(self):
        # Patterns for Indian PII
        self.patterns = {
            "phone": r"\+?91?[-\s]?\d{10}",
            "aadhaar": r"\d{4}[-\s]?\d{4}[-\s]?\d{4}",
            "pan": r"[A-Z]{5}\d{4}[A-Z]",
            "pincode": r"\b\d{6}\b",
            "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        }
        
        # Common name patterns (Indian names)
        self.name_titles = ["mr", "mrs", "ms", "shri", "smt", "dr", "prof"]
        
    def redact(self, text: str, user_internal_id: Optional[str] = None) -> str:
        """
        Redact PII from text before sending to LLM
        
        Args:
            text: Input text that may contain PII
            user_internal_id: Optional internal ID to use as replacement
            
        Returns:
            Text with PII redacted
        """
        redacted = text
        
        # Redact phone numbers
        redacted = re.sub(
            self.patterns["phone"],
            "[PHONE_REDACTED]",
            redacted
        )
        
        # Redact Aadhaar
        redacted = re.sub(
            self.patterns["aadhaar"],
            "[AADHAAR_REDACTED]",
            redacted
        )
        
        # Redact PAN
        redacted = re.sub(
            self.patterns["pan"],
            "[PAN_REDACTED]",
            redacted
        )
        
        # Redact email
        redacted = re.sub(
            self.patterns["email"],
            "[EMAIL_REDACTED]",
            redacted
        )
        
        return redacted
    
    def generate_internal_id(self, phone_number: str) -> str:
        """
        Generate consistent internal ID from phone number
        Used instead of real phone in LLM prompts
        """
        # Create a hash-based ID
        hash_input = f"sahayak_{phone_number}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        return f"user_{hash_value}"
    
    def mask_phone(self, phone: str) -> str:
        """
        Partially mask phone number for display
        +91 98765 43210 -> +91 98*** ***10
        """
        digits = re.sub(r"\D", "", phone)
        if len(digits) >= 10:
            return f"+91 {digits[-10:-7]}** ***{digits[-2:]}"
        return phone
    
    def redact_for_logging(self, data: dict) -> dict:
        """
        Redact PII from log data
        Used before writing to logs
        """
        redacted = data.copy()
        
        sensitive_fields = [
            "phone_number", "full_name", "address", 
            "aadhaar", "pan", "email", "caregiver_phone"
        ]
        
        for field in sensitive_fields:
            if field in redacted:
                if field == "phone_number":
                    redacted[field] = self.mask_phone(redacted[field])
                elif field == "full_name":
                    # Keep only first name initial
                    name = redacted[field]
                    redacted[field] = f"{name[0]}***" if name else "[REDACTED]"
                else:
                    redacted[field] = "[REDACTED]"
        
        return redacted


class AuditLogger:
    """
    Secure audit logging with PII protection
    """
    
    def __init__(self):
        self.redactor = PIIRedactor()
        
    def log_call_event(
        self,
        call_id: str,
        event_type: str,
        data: dict,
        user_internal_id: str
    ) -> dict:
        """
        Create audit log entry with PII redacted
        
        Returns log packet structure from Phase 5 & 6
        """
        redacted_data = self.redactor.redact_for_logging(data)
        
        return {
            "call_id": call_id,
            "user_id": user_internal_id,  # Internal ID only
            "event_type": event_type,
            "data": redacted_data,
            "timestamp": datetime.utcnow().isoformat()
        }