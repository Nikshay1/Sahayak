"""
System Constants and Response Templates
Designed for elderly users - polite, respectful language
"""

# Intent Types
class IntentType:
    ORDER_MEDICINE = "ORDER_MEDICINE"
    CHECK_BALANCE = "CHECK_BALANCE"
    ORDER_STATUS = "ORDER_STATUS"
    UNKNOWN = "UNKNOWN"


# Urgency Levels
class UrgencyLevel:
    STANDARD = "standard"
    IMMEDIATE = "immediate"


# Transaction Types
class TransactionType:
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"
    REFUND = "REFUND"


# Voice Response Templates (Polite, Elderly-Friendly)
class VoiceResponses:
    # Greetings
    GREETING = "Namaste {name}. Yes, I am here. How can I help you today?"
    
    # Clarification (Good - not "Input invalid. Repeat.")
    CLARIFICATION_MEDICINE = (
        "I heard you want medicine, but the name wasn't clear. "
        "Could you say the name of the tablet again?"
    )
    CLARIFICATION_QUANTITY = (
        "I understood you need {medicine}. "
        "How many strips or tablets would you like?"
    )
    
    # Confirmation
    ORDER_CONFIRMATION = (
        "I can see you usually order {medicine}. "
        "A strip of {quantity} costs {price} rupees. "
        "Shall I order it to your home in {address}?"
    )
    
    # Wallet Feedback
    ORDER_COMPLETE = (
        "Done. I have paid {amount} rupees from your wallet. "
        "Your new balance is {balance} rupees. "
        "The chemist will deliver it by {delivery_time}."
    )
    BALANCE_CHECK = (
        "Your current balance is {balance} rupees. "
        "You have enough for {estimate} more orders."
    )
    INSUFFICIENT_BALANCE = (
        "I'm sorry, but your wallet balance of {balance} rupees "
        "is not enough for this order of {amount} rupees. "
        "Please ask your family member to add money to your Sahayak wallet."
    )
    
    # Safe Refusal
    SAFE_REFUSAL = (
        "I did not understand clearly. "
        "Please call your caregiver for help, or try saying it again slowly."
    )
    
    # Unsupported Actions
    EMERGENCY_REDIRECT = (
        "This sounds like an emergency. "
        "Please dial 112 immediately for emergency services. "
        "I cannot help with emergencies."
    )
    UNSUPPORTED_ACTION = (
        "I'm sorry, I can only help you order medicines and check your balance. "
        "For other things, please contact your family member."
    )
    
    # Cost Confirmation
    COST_CONFIRMATION = "The cost is {amount} rupees. Should I proceed?"
    
    # Errors
    API_ERROR = (
        "I'm having trouble placing your order right now. "
        "Your money is safe. Please try again in a few minutes."
    )


# Log Event Types
class LogEventType:
    CALL_STARTED = "CALL_STARTED"
    AUDIO_RECEIVED = "AUDIO_RECEIVED"
    TRANSCRIPTION_COMPLETE = "TRANSCRIPTION_COMPLETE"
    INTENT_DETECTED = "INTENT_DETECTED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    WALLET_CHECKED = "WALLET_CHECKED"
    WALLET_LOCKED = "WALLET_LOCKED"
    WALLET_DEBITED = "WALLET_DEBITED"
    WALLET_REFUNDED = "WALLET_REFUNDED"
    ORDER_PLACED = "ORDER_PLACED"
    ORDER_FAILED = "ORDER_FAILED"
    CALL_ENDED = "CALL_ENDED"