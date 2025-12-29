"""
Database Models - PostgreSQL with Double-Entry Ledger Pattern
Phase 3: Prepaid Wallet System
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, 
    ForeignKey, Text, Enum, Index, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from datetime import datetime
import uuid
import enum

from src.db.database import Base


class TransactionType(enum.Enum):
    CREDIT = "CREDIT"
    DEBIT = "DEBIT"
    LOCK = "LOCK"
    UNLOCK = "UNLOCK"
    REFUND = "REFUND"


class ExecutionStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class User(Base):
    """
    User model with cached balance
    PII is stored but never sent to LLM - use internal UUID
    """
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    internal_id = Column(String(20), unique=True, nullable=False)  # e.g., "user_8821"
    phone_number = Column(String(15), unique=True, nullable=False, index=True)
    full_name = Column(String(100), nullable=False)  # PII - never sent to LLM
    
    # Address for delivery
    address_line1 = Column(String(200))
    address_line2 = Column(String(200))
    city = Column(String(50))
    pincode = Column(String(10))
    
    # Caregiver contact for notifications
    caregiver_phone = Column(String(15))
    caregiver_name = Column(String(100))
    
    # Wallet - cached balance (source of truth is ledger)
    current_balance = Column(Integer, default=0)  # In smallest currency unit (paise)
    locked_balance = Column(Integer, default=0)   # Reserved for pending transactions
    
    # User preferences (learned over time)
    preferred_language = Column(String(10), default="hi")  # Hindi default
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)
    
    # Relationships
    ledger_entries = relationship("LedgerEntry", back_populates="user")
    orders = relationship("Order", back_populates="user")
    medicine_history = relationship("UserMedicineHistory", back_populates="user")
    call_logs = relationship("CallLog", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.internal_id}>"


class LedgerEntry(Base):
    """
    Double-Entry Ledger - Financial data is NEVER overwritten, only appended
    Phase 3: Task 3.1 - Wallet Ledger Architecture
    """
    __tablename__ = "ledger_entries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(String(50), nullable=False, index=True)  # Groups related entries
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    amount = Column(Integer, nullable=False)  # Always positive, in paise
    transaction_type = Column(Enum(TransactionType), nullable=False)
    
    # Reference to what caused this entry
    reference_type = Column(String(50))  # "ORDER", "TOPUP", "REFUND"
    reference_id = Column(UUID(as_uuid=True))
    
    # Running balance after this entry (for quick audits)
    balance_after = Column(Integer, nullable=False)
    
    description = Column(String(200))
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="ledger_entries")
    
    __table_args__ = (
        CheckConstraint('amount >= 0', name='positive_amount'),
        Index('idx_ledger_user_timestamp', 'user_id', 'timestamp'),
    )


class Order(Base):
    """
    Medicine Orders
    Phase 4: API Orchestration
    """
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String(20), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    call_id = Column(UUID(as_uuid=True), ForeignKey("call_logs.id"))
    
    # Order details
    items = Column(JSONB, nullable=False)  # [{name, sku, quantity, price}]
    total_amount = Column(Integer, nullable=False)  # In paise
    
    # Delivery
    delivery_address = Column(Text)
    estimated_delivery = Column(DateTime(timezone=True))
    
    # Status tracking
    execution_status = Column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING)
    external_order_id = Column(String(100))  # From pharmacy API
    
    # Wallet transaction reference
    transaction_id = Column(String(50))
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationships
    user = relationship("User", back_populates="orders")
    call = relationship("CallLog", back_populates="order")


class UserMedicineHistory(Base):
    """
    Track medicines user has ordered before
    For intelligent suggestions: "I see you usually order Atorvastatin"
    """
    __tablename__ = "user_medicine_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    medicine_name = Column(String(100), nullable=False)
    medicine_sku = Column(String(50))
    generic_name = Column(String(100))
    
    # Usage patterns
    last_ordered = Column(DateTime(timezone=True))
    order_count = Column(Integer, default=1)
    typical_quantity = Column(Integer)
    
    # Aliases user has used
    user_aliases = Column(JSONB, default=list)  # ["heart medicine", "BP tablet"]
    
    user = relationship("User", back_populates="medicine_history")
    
    __table_args__ = (
        Index('idx_medicine_history_user', 'user_id'),
    )


class CallLog(Base):
    """
    End-to-End Call Logging
    Phase 5 & 6: Task 6.1 - Debugging and Safety Audit
    """
    __tablename__ = "call_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(String(50), unique=True, nullable=False)  # External call ID
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    
    # Audio storage (S3 or similar)
    input_audio_url = Column(String(500))
    
    # Transcription
    transcribed_text = Column(Text)
    transcription_confidence = Column(Float)
    
    # Intent
    intent_detected = Column(String(50))
    intent_confidence = Column(Float)
    parsed_intent = Column(JSONB)  # Full IntentSchema
    
    # Wallet
    wallet_status = Column(String(20))  # "APPROVED", "DENIED", "INSUFFICIENT"
    
    # Execution
    execution_status = Column(String(20))  # "SUCCESS", "FAILED", "REFUNDED"
    
    # Timing
    call_started_at = Column(DateTime(timezone=True))
    call_ended_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Integer)
    
    # Raw event log
    events = Column(JSONB, default=list)  # Append-only event stream
    
    # Error tracking
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="call_logs")
    order = relationship("Order", back_populates="call", uselist=False)


class MedicineCatalog(Base):
    """
    Known medicines for the mocked pharmacy API
    """
    __tablename__ = "medicine_catalog"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sku = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    generic_name = Column(String(100))
    
    # Common aliases for fuzzy matching
    aliases = Column(JSONB, default=list)  # ["calcium tablet", "haddi ki dawai"]
    
    # Pricing
    price_per_unit = Column(Integer, nullable=False)  # In paise
    units_per_strip = Column(Integer, default=10)
    
    # Availability
    is_available = Column(Boolean, default=True)
    requires_prescription = Column(Boolean, default=False)
    
    category = Column(String(50))  # "cardiac", "diabetes", "supplements"